import Foundation
import CoreGraphics
import AppKit

// Exporta PDF a tamaño real (25×20 cm por página = 708.661×566.929 pt), PNG por
// hoja y reporte.md con el conteo (piezas + hechas + reportadas).
enum Exporter {

    static let pageWpt = 25.0 / 2.54 * 72.0   // 708.661
    static let pageHpt = 20.0 / 2.54 * 72.0   // 566.929

    static func exportAll(_ project: Project, outDir: URL) throws -> (pdf: URL, pngs: [URL], base: String) {
        let nHojas = project.sheets.filter { $0.kind == "hoja" }.count
        let nGuias = project.sheets.filter { $0.kind == "guia" }.count
        let base = "FOTOS COMESTIBLES \(project.week) · \(nHojas) hojas + \(nGuias) guías (no imprimir)"
        try FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)
        let pdfURL = outDir.appendingPathComponent(base + ".pdf")
        let pngDir = outDir.appendingPathComponent(base, isDirectory: true)
        try FileManager.default.createDirectory(at: pngDir, withIntermediateDirectories: true)

        var images: [CGImage] = []
        var pngs: [URL] = []
        for (i, s) in project.sheets.enumerated() {
            guard let cg = SheetRenderer.renderCGImage(project, s, guides: false) else { continue }
            images.append(cg)
            let kind = s.kind == "guia" ? "GUIA" : "hoja"
            let name = String(format: "%02d_%@_%@.png", i + 1, kind, (s.size.isEmpty ? s.title : s.size).replacingOccurrences(of: " ", with: "_"))
            let url = pngDir.appendingPathComponent(name)
            let img = NSImage(cgImage: cg, size: NSSize(width: Config.sheetW, height: Config.sheetH))
            if let tiff = img.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff), let png = rep.representation(using: .png, properties: [:]) {
                try png.write(to: url)
                pngs.append(url)
            }
        }

        // PDF: cada página 25×20 cm, imagen 945×756 dibujada a escala exacta
        let mediaBox = CGRect(x: 0, y: 0, width: pageWpt, height: pageHpt)
        let data = NSMutableData()
        guard let pdf = CGContext(consumer: CGDataConsumer(data: data as CFMutableData), mediaBox: mediaBox, nil) else {
            throw NSError(domain: "export", code: 1, userInfo: [NSLocalizedDescriptionKey: "no se pudo crear el contexto PDF"])
        }
        for cg in images {
            pdf.beginPDFPage(nil)
            pdf.translateBy(x: 0, y: pageHpt)
            pdf.scaleBy(x: pageWpt / Config.sheetW, y: -pageHpt / Config.sheetH)
            pdf.draw(cg, in: CGRect(x: 0, y: 0, width: Config.sheetW, height: Config.sheetH))
            pdf.endPDFPage()
        }
        pdf.closePDF()
        try data.write(to: pdfURL as URL)
        return (pdfURL, pngs, base)
    }

    static func buildReport(_ project: Project, problems: [String]) -> String {
        var lines: [String] = []
        let week = project.week.isEmpty ? "semana" : project.week
        lines.append("# Reporte · FOTOS COMESTIBLES \(week)")
        lines.append("")
        let nHojas = project.sheets.filter { $0.kind == "hoja" }.count
        let nGuias = project.sheets.filter { $0.kind == "guia" }.count
        lines.append("**\(nHojas) hojas + \(nGuias) guías (no imprimir).** Zona útil 21×16 cm, guías a 2 cm, gap ≥ 0.5 cm.")
        lines.append("")
        lines.append("## Piezas por hoja")
        for (i, s) in project.sheets.enumerated() {
            lines.append("### \(i + 1). \(s.title)")
            let ps = project.pieces.filter { $0.sheetId == s.id }
            if ps.isEmpty { lines.append("- (vacía)") }
            for p in ps {
                var flags: [String] = []
                if p.gorrito { flags.append("GORRITO") }
                if p.bn { flags.append("B/N") }
                let fl = flags.isEmpty ? "" : " · " + flags.joined(separator: " · ")
                let first = p.label.split(separator: "\n").first.map(String.init) ?? ""
                let last = p.label.split(separator: "\n").count > 1 ? p.label.split(separator: "\n").last.map(String.init) ?? "" : ""
                lines.append("- `\(first)` @ (\(Int(p.x)),\(Int(p.y))) \(String(format: "%.1f", p.w / Config.pxPerCm))×\(String(format: "%.1f", p.h / Config.pxPerCm)) cm\(fl) — \(last)")
                if let cg = PhotoStore.shared.cgImage(p.photo), let ib = p.imgBox, ib.width > 0, ib.width < p.w {
                    lines.append("  - ⚠ foto puede salir pixeleada (fuente \(Int(ib.width))px < pieza \(Int(p.w))px); pedir original")
                }
                _ = cg
            }
            lines.append("")
        }
        let pend = project.pieces.filter { $0.pending }
        let withPhoto = project.orders.filter { $0.mode != nil || !$0.edibleLinks.isEmpty }
        let hechas = project.orders.filter { $0.status == "hecha" }
        let excluidos = project.orders.filter { $0.status == "excluida" }
        let enHojas = project.pieces.filter { !$0.pending }.count
        lines.append("## Pedidos con foto comestible: conteo (piezas + hechos + reportados)")
        lines.append("- Pedidos con foto comestible en Craft: **\(withPhoto.count)**")
        lines.append("- Piezas en hojas: **\(enHojas)** · hechos aparte: **\(hechas.count)** · reportados fuera: **\(pend.count + excluidos.count)** (total \(enHojas + hechas.count + pend.count + excluidos.count))")
        if !pend.isEmpty {
            lines.append("")
            lines.append("## PENDIENTE (foto sin acceso / sin imagen)")
            for p in pend {
                let o = project.orders.first { $0.id == p.orderId }
                lines.append("- \(o?.labelId ?? p.id): \(p.photoStatus) — \(o?.edibleLinks ?? [])")
            }
        }
        if !excluidos.isEmpty {
            lines.append("")
            lines.append("## Reportados fuera")
            for o in excluidos {
                lines.append("- \(o.labelId): \(o.statusReason)")
            }
        }
        if !problems.isEmpty {
            lines.append("")
            lines.append("## ⚠ Problemas de acomodo")
            for pr in problems { lines.append("- \(pr)") }
        }
        return lines.joined(separator: "\n") + "\n"
    }
}
