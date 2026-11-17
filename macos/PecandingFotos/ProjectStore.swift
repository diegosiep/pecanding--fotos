import Foundation
import AppKit

// Estado observable del proyecto; persiste project.json en Application Support
// (mismo formato JSON que la app Python, para poder compartir estado).
final class ProjectStore: ObservableObject {
    @Published var project = Project()
    @Published var selectedPieceId: String?
    @Published var selectedSheetId: String?
    @Published var encuadreMode = false
    @Published var statusMessage = ""
    @Published var renderVersion = 0

    let photos = PhotoStore.shared

    init() { load() }

    func bump() { renderVersion &+= 1 }

    // MARK: - persistencia

    func load() {
        guard let data = try? Data(contentsOf: photos.projectFile),
              let p = try? JSONDecoder().decode(Project.self, from: data) else { return }
        project = p
    }

    func save() {
        let enc = JSONEncoder()
        enc.outputFormatting = [.prettyPrinted, .sortedKeys]
        guard let data = try? enc.encode(project) else { return }
        try? data.write(to: photos.projectFile)
    }

    // MARK: - importación Craft

    func importCraft(text: String, sourceName: String, week: String?) -> (week: String, weeks: [String], orders: Int, error: String?) {
        let pages = CraftParser.parseCraftMarkdown(text)
        let weeks = pages.keys.sorted()
        guard !pages.isEmpty else { return ("", weeks, 0, "no se encontraron páginas") }
        let w = week ?? CraftParser.currentWeekTitle(weeks) ?? weeks.first!
        guard let page = pages[w] else {
            return ("", weeks, 0, "Semana «\(w)» no encontrada. Disponibles: \(weeks.joined(separator: " | "))")
        }
        project = Project(week: w, sourceName: sourceName, orders: page.orders, pieces: [], sheets: [], photos: [:])
        save()
        bump()
        return (w, weeks, page.orders.count, nil)
    }

    // MARK: - preparación

    func prepare(fetch: Bool) async {
        for o in project.orders {
            guard o.mode != nil || !o.edibleLinks.isEmpty else { continue }
            guard o.status != "hecha", o.status != "excluida" else { continue }
            let links = o.edibleLinks
            if o.imageMissing && links.isEmpty {
                updateOrder(o.id) { $0.status = "pendiente"; $0.statusReason = "el formulario no trae la imagen" }
            }
            for (i, url) in links.enumerated() {
                var rec = project.photos[url]
                if rec == nil {
                    if fetch {
                        rec = await photos.download(url)
                    } else {
                        rec = PhotoRec(status: "sin_acceso", srcUrl: url)
                    }
                    project.photos[url] = rec
                }
                if let r = rec, r.bn { updateOrder(o.id) { $0.bn = true } }
                let piece = newPieceForOrder(project.orders.first { $0.id == o.id } ?? o,
                                             photo: (rec?.status == "ok" || rec?.status == "subida") ? rec?.path : nil,
                                             photoStatus: rec?.status ?? "sin_acceso", index: i, total: links.count)
                var piece = piece
                if piece.kind == "cutout", let path = rec?.path, !path.isEmpty {
                    fitCutout(&piece)
                }
                project.pieces.append(piece)
            }
            if !links.isEmpty { updateOrder(o.id) { $0.status = "lista" } }
        }
        await MainActor.run {
            LayoutEngine.autoLayout(&project)
            save()
            bump()
            statusMessage = "piezas: \(project.pieces.count)"
        }
    }

    func fetchOrder(_ id: String) async {
        guard let o = project.orders.first(where: { $0.id == id }) else { return }
        var results: [String: String] = [:]
        for url in o.edibleLinks {
            let rec = await photos.download(url)
            project.photos[url] = rec
            results[url] = rec.status
            if rec.bn { updateOrder(id) { $0.bn = true } }
        }
        for url in o.refLinks where project.photos[url] == nil {
            let rec = await photos.download(url)
            project.photos[url] = rec
            if rec.status == "ok", rec.bn { updateOrder(id) { $0.bn = true } }
        }
        for i in project.pieces.indices where project.pieces[i].orderId == id {
            for (url, rec) in project.photos where rec.status == "ok" || rec.status == "subida", o.edibleLinks.contains(url) {
                project.pieces[i].photo = rec.path
                project.pieces[i].photoStatus = rec.status
                project.pieces[i].pending = false
            }
        }
        if !o.edibleLinks.isEmpty { updateOrder(id) { $0.status = "lista" } }
        await MainActor.run { save(); bump() }
    }

    func upload(_ orderId: String, data: Data, filename: String) {
        guard let rec = photos.saveUpload(data: data, filename: filename),
              let o = project.orders.first(where: { $0.id == orderId }) else { return }
        let url = "local://" + filename
        project.photos[url] = rec
        if !o.edibleLinks.contains(url) {
            updateOrder(orderId) { $0.edibleLinks.append(url); $0.status = "lista"; if rec.bn { $0.bn = true } }
        }
        for i in project.pieces.indices where project.pieces[i].orderId == orderId && project.pieces[i].pending {
            project.pieces[i].photo = rec.path
            project.pieces[i].photoStatus = "subida"
            project.pieces[i].pending = false
            if rec.bn { project.pieces[i].bn = true }
            break
        }
        save(); bump()
    }

    func createPiece(_ orderId: String) {
        guard let o = project.orders.first(where: { $0.id == orderId }) else { return }
        let url = o.edibleLinks.first ?? ""
        let rec = project.photos[url]
        var p = newPieceForOrder(o, photo: rec?.path, photoStatus: rec?.status ?? "sin_acceso")
        if p.kind == "cutout", let path = rec?.path, !path.isEmpty { fitCutout(&p) }
        project.pieces.append(p)
        LayoutEngine.autoLayout(&project)
        save(); bump()
    }

    func setOrderStatus(_ id: String, _ status: String, _ reason: String) {
        updateOrder(id) { $0.status = status; $0.statusReason = reason }
        for i in project.pieces.indices where project.pieces[i].orderId == id {
            project.pieces[i].pending = (status == "excluida")
        }
        LayoutEngine.autoLayout(&project)
        save(); bump()
    }

    func updateOrder(_ id: String, _ block: (inout Order) -> Void) {
        guard let i = project.orders.firstIndex(where: { $0.id == id }) else { return }
        block(&project.orders[i])
        for j in project.pieces.indices where project.pieces[j].orderId == id {
            project.pieces[j].size = project.orders[i].size.isEmpty ? project.pieces[j].size : project.orders[i].size
            project.pieces[j].day = project.orders[i].day
            project.pieces[j].gorrito = project.orders[i].gorrito
            project.pieces[j].bn = project.orders[i].bn
        }
        save(); bump()
    }

    func updatePiece(_ id: String, _ block: (inout Piece) -> Void) {
        guard let i = project.pieces.firstIndex(where: { $0.id == id }) else { return }
        block(&project.pieces[i])
        save(); bump()
    }

    func deletePiece(_ id: String) {
        project.pieces.removeAll { $0.id == id }
        if selectedPieceId == id { selectedPieceId = nil }
        save(); bump()
    }

    func autoLayout() {
        LayoutEngine.autoLayout(&project)
        save(); bump()
    }

    func addSheet(title: String) {
        project.sheets.append(Sheet(title: title, kind: "hoja"))
        if selectedSheetId == nil { selectedSheetId = project.sheets.last?.id }
        save(); bump()
    }

    func deleteSheet(_ id: String) {
        project.sheets.removeAll { $0.id == id }
        for i in project.pieces.indices where project.pieces[i].sheetId == id {
            project.pieces[i].sheetId = ""
        }
        save(); bump()
    }

    // MARK: - quitar fondo (Vision)

    func removeBackground(_ pieceId: String, headOnly: Bool) async -> String? {
        guard let idx = project.pieces.firstIndex(where: { $0.id == pieceId }),
              let cg = photos.cgImage(project.pieces[idx].photo) else { return "pieza sin foto" }
        let result = VisionCutout.analyze(cg)
        guard let mask = result.pixelBuffer, let cut = VisionCutout.applyMask(cg, mask) else {
            return "Vision no encontró persona; la pieza queda como foto en caja"
        }
        let box = headOnly ? (result.head ?? result.subject) : result.subject
        guard let b = box else { return "no se encontró sujeto en la máscara" }
        // guardar el cutout como PNG con alfa
        let name = "cut_" + UUID().uuidString.prefix(12) + ".png"
        let dest = photos.photosDir.appendingPathComponent(String(name))
        let img = NSImage(cgImage: cut, size: NSSize(width: cg.width, height: cg.height))
        if let tiff = img.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff), let png = rep.representation(using: .png, properties: [:]) {
            try? png.write(to: dest)
        }
        await MainActor.run {
            let W = Double(cg.width), H = Double(cg.height)
            let mw = b.width * 0.02, mh = b.height * 0.02
            let ib = ImgBox(left: max(0, b.minX - mw), top: max(0, b.minY - mh),
                           width: min(W, b.width + 2 * mw), height: min(H, b.height + 2 * mh))
            let scale = project.pieces[idx].h / ib.height
            project.pieces[idx].photo = "photos/\(name)"
            project.pieces[idx].hasMask = true
            project.pieces[idx].headOnly = headOnly
            project.pieces[idx].imgBox = ib
            project.pieces[idx].w = max(10, ib.width * scale)
            save(); bump()
        }
        return nil
    }

    /// Ajusta img_box/w al sujeto medido (con Vision si hay persona; si no, caja completa).
    func fitCutout(_ p: inout Piece) {
        guard let cg = photos.cgImage(p.photo) else { return }
        let W = Double(cg.width), H = Double(cg.height)
        let result = VisionCutout.analyze(cg)
        if let b = result.subject {
            let mw = b.width * 0.02, mh = b.height * 0.02
            let ib = ImgBox(left: max(0, b.minX - mw), top: max(0, b.minY - mh),
                           width: min(W, b.width + 2 * mw), height: min(H, b.height + 2 * mh))
            let scale = p.h / ib.height
            p.imgBox = ib
            p.w = max(10, ib.width * scale)
            p.hasMask = true
            return
        }
        p.imgBox = ImgBox(left: 0, top: 0, width: W, height: H)
        p.w = max(10, W * (p.h / H))
    }

    // MARK: - exportar

    func export() -> (String, [String]) {
        let problems = LayoutEngine.checkLayout(project)
        let out = photos.outDir
        guard let res = try? Exporter.exportAll(project, outDir: out) else {
            return ("error al exportar", problems)
        }
        let report = Exporter.buildReport(project, problems: problems)
        let reportURL = out.appendingPathComponent(res.base).appendingPathComponent("reporte.md")
        try? FileManager.default.createDirectory(at: out.appendingPathComponent(res.base), withIntermediateDirectories: true)
        try? report.write(to: reportURL, atomically: true, encoding: .utf8)
        NSWorkspace.shared.activateFileViewerSelecting([res.pdf])
        return (res.pdf.path, problems)
    }
}
