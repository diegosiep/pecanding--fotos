import Foundation
import CoreGraphics
import CoreImage
import AppKit

// Renderiza hojas 945×756 px (mismo resultado que la app Python): círculos con
// contorno negro 1 px, recortadas con alfa, etiquetas 12 px, guías punteadas
// (solo en preview) y hojas GUÍA 1:1.
enum SheetRenderer {

    static func renderCGImage(_ project: Project, _ sheet: Sheet, guides: Bool) -> CGImage? {
        if sheet.kind == "guia" { return renderGuia(sheet.size) }
        guard let ctx = makeContext() else { return nil }
        paintWhite(ctx)
        if guides {
            dashedLine(ctx, (Config.guide, 0), (Config.guide, Config.sheetH), gray: 200)
            dashedLine(ctx, (0, Config.guide), (Config.sheetW, Config.guide), gray: 200)
            dashedLine(ctx, (Config.safeRight, 0), (Config.safeRight, Config.sheetH), gray: 225)
            dashedLine(ctx, (0, Config.safeBottom), (Config.sheetW, Config.safeBottom), gray: 225)
        }
        let ps = project.pieces.filter { $0.sheetId == sheet.id && !$0.pending }
        for p in ps { drawPiece(ctx, project, p) }
        for p in ps { drawLabel(ctx, p) }
        return ctx.makeImage()
    }

    static func makeContext() -> CGContext? {
        let w = Int(Config.sheetW), h = Int(Config.sheetH)
        let cs = CGColorSpaceCreateDeviceRGB()
        guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w * 4, space: cs, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return nil }
        // origen arriba-izquierda como en la app Python
        ctx.translateBy(x: 0, y: Config.sheetH)
        ctx.scaleBy(x: 1, y: -1)
        return ctx
    }

    static func paintWhite(_ ctx: CGContext) {
        ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1)!)
        ctx.fill(CGRect(x: 0, y: 0, width: Config.sheetW, height: Config.sheetH))
    }

    static func dashedLine(_ ctx: CGContext, _ p1: (Double, Double), _ p2: (Double, Double), gray: CGFloat) {
        ctx.setStrokeColor(CGColor(red: gray / 255, green: gray / 255, blue: gray / 255, alpha: 1)!)
        ctx.setLineWidth(1)
        ctx.setLineDash(phase: 0, lengths: [8, 6])
        ctx.beginPath()
        ctx.move(to: CGPoint(x: p1.0, y: p1.1))
        ctx.addLine(to: CGPoint(x: p2.0, y: p2.1))
        ctx.strokePath()
        ctx.setLineDash(phase: 0, lengths: [])
    }

    static func drawText(_ ctx: CGContext, _ text: String, _ x: Double, _ y: Double, size: Double = Config.labelFontPx, bold: Bool = false, color: CGColor? = nil) -> Double {
        let font = CTFontCreateWithName(bold ? "Helvetica-Bold" : "Helvetica" as CFString, CGFloat(size), nil)
        let attr: [CFAttributedString.Key: Any] = [.font: font, .foregroundColor: color ?? CGColor(black: 0, alpha: 1)!]
        let line = CTLineCreateWithAttributedString(CFAttributedStringCreate(nil, text as CFString, attr as CFDictionary)!)
        ctx.textPosition = CGPoint(x: x, y: y)
        CTLineDraw(line, ctx)
        return CTLineGetTypographicBounds(line, nil, nil, nil).width
    }

    static func textWidth(_ text: String, size: Double = Config.labelFontPx, bold: Bool = false) -> Double {
        let font = CTFontCreateWithName(bold ? "Helvetica-Bold" : "Helvetica" as CFString, CGFloat(size), nil)
        let attr: [CFAttributedString.Key: Any] = [.font: font]
        let line = CTLineCreateWithAttributedString(CFAttributedStringCreate(nil, text as CFString, attr as CFDictionary)!)
        return CTLineGetTypographicBounds(line, nil, nil, nil).width
    }

    // MARK: - piezas

    static func imgBox(_ p: Piece, _ im: CGImage) -> ImgBox {
        if let ib = p.imgBox, ib.width > 0, ib.height > 0 { return ib }
        if p.kind == "circle" {
            let side = Double(min(im.width, im.height))
            return ImgBox(left: (Double(im.width) - side) / 2, top: (Double(im.height) - side) / 2, width: side, height: side)
        }
        return ImgBox(left: 0, top: 0, width: Double(im.width), height: Double(im.height))
    }

    static func croppedSource(_ im: CGImage, _ ib: ImgBox, _ w: Double, _ h: Double, bn: Bool) -> CGImage? {
        let W = Double(im.width), H = Double(im.height)
        let left = max(0, min(ib.left, W - 1))
        let top = max(0, min(ib.top, H - 1))
        let width = max(1, min(ib.width, W - left))
        let height = max(1, min(ib.height, H - top))
        guard let crop = im.cropping(to: CGRect(x: left, y: top, width: width, height: height)) else { return nil }
        var out = crop
        if bn {
            let ci = CIImage(cgImage: crop)
            if let f = CIFilter(name: "CIColorControls") {
                f.setValue(ci, forKey: kCIInputImageKey)
                f.setValue(0, forKey: kCIInputSaturationKey)
                if let o = f.outputImage, let cg2 = CIContext().createCGImage(o, from: o.extent) {
                    out = cg2
                }
            }
        }
        return out
    }

    static func drawPiece(_ ctx: CGContext, _ project: Project, _ p: Piece) {
        guard let cg = PhotoStore.shared.cgImage(p.photo), let src = croppedSource(cg, imgBox(p, cg), p.w, p.h, bn: p.bn) else {
            ctx.setStrokeColor(CGColor(red: 0.78, green: 0.24, blue: 0.24, alpha: 1)!)
            ctx.setLineWidth(2)
            ctx.stroke(CGRect(x: p.x, y: p.y, width: p.w, height: p.h))
            drawText(ctx, "SIN FOTO", p.x + 4, p.y + 4)
            return
        }
        ctx.saveGState()
        if abs(p.rotation) > 0.5 {
            let cx = p.x + p.effW / 2, cy = p.y + p.effH / 2
            ctx.translateBy(x: cx, y: cy)
            ctx.rotate(by: -p.rotation * .pi / 180)
            ctx.translateBy(x: -cx, y: -cy)
        }
        if p.kind == "circle" {
            let rect = CGRect(x: p.x, y: p.y, width: p.w, height: p.h)
            ctx.saveGState()
            ctx.beginPath()
            ctx.addEllipse(in: rect)
            ctx.clip()
            ctx.interpolationQuality = .high
            ctx.draw(src, in: rect)
            ctx.restoreGState()
            ctx.setStrokeColor(CGColor(black: 0, alpha: 1)!)
            ctx.setLineWidth(1)
            ctx.beginPath()
            ctx.addEllipse(in: rect)
            ctx.strokePath()
        } else {
            ctx.interpolationQuality = .high
            ctx.draw(src, in: CGRect(x: p.x, y: p.y, width: p.w, height: p.h))
        }
        ctx.restoreGState()
    }

    static func drawLabel(_ ctx: CGContext, _ p: Piece) {
        let lines = p.label.split(separator: "\n").map(String.init)
        guard !lines.isEmpty else { return }
        let lh = Config.labelFontPx * Config.labelLineHeight
        let tw = lines.map { textWidth($0) }.max() ?? 0
        let th = lh * Double(lines.count)
        var lx = p.x, ly = p.y + p.effH + 5
        if ly + th > Config.sheetH - 2 {
            lx = p.x + p.effW + 5
            ly = p.y
            if lx + tw > Config.sheetW - 2 {
                lx = p.x
                ly = p.y - th - 4
                if ly < 0 { lx = max(2, Config.sheetW - tw - 2); ly = Config.sheetH - th - 2 }
            }
        }
        lx = max(2, min(lx, Config.sheetW - tw - 2))
        for (i, t) in lines.enumerated() {
            drawText(ctx, t, lx, ly + Double(i) * lh)
        }
    }

    // MARK: - hoja GUÍA 1:1

    static func renderGuia(_ size: String) -> CGImage? {
        guard let spec = Config.sizes[size], let ctx = makeContext() else { return nil }
        paintWhite(ctx)
        let recCm = (spec.recortadaCm.0 + spec.recortadaCm.1) / 2
        let title = "GUÍA \(size.uppercased()) · NO IMPRIMIR · tamaño real 1:1 — pastel Ø \(spec.circleCm) cm · recortada ≈ \(recCm) cm · con gorrito ≈ \(spec.gorritoCm) cm"
        drawText(ctx, title, Config.safeLeft, 14, bold: true)
        let dia = Config.cm(spec.circleCm)
        let cy = min(Config.safeTop, Config.sheetH - Config.pageMinMargin - dia)
        let gray = CGColor(red: 138 / 255, green: 138 / 255, blue: 138 / 255, alpha: 1)!
        ctx.setFillColor(CGColor(red: 244 / 255, green: 244 / 255, blue: 244 / 255, alpha: 1)!)
        ctx.setStrokeColor(gray)
        ctx.setLineWidth(2)
        ctx.beginPath()
        ctx.addEllipse(in: CGRect(x: Config.safeLeft, y: cy, width: dia, height: dia))
        ctx.drawPath(using: .fillStroke)
        drawText(ctx, "COMPLETA Ø \(spec.circleCm) cm", Config.safeLeft + 6, cy + 6, color: CGColor(red: 90 / 255, green: 90 / 255, blue: 90 / 255, alpha: 1))
        // rectángulo de la recortada centrado en el círculo
        let rh = Config.cm(recCm)
        let rw = 0.5 * rh
        let cx = Config.safeLeft + dia / 2
        let cyy = cy + dia / 2
        ctx.setFillColor(CGColor(red: 218 / 255, green: 218 / 255, blue: 218 / 255, alpha: 1)!)
        ctx.setStrokeColor(CGColor(red: 60 / 255, green: 60 / 255, blue: 60 / 255, alpha: 1)!)
        ctx.setLineWidth(1)
        let rr = CGRect(x: cx - rw / 2, y: cyy - rh / 2, width: rw, height: rh)
        let path = CGPath(roundedRect: rr, cornerWidth: 8, cornerHeight: 8, transform: nil)
        ctx.addPath(path)
        ctx.drawPath(using: .fillStroke)
        for (i, t) in ["RECORTADA", "≈ \(recCm) cm", "(gorrito \(spec.gorritoCm))"].enumerated() {
            let tw = textWidth(t)
            drawText(ctx, t, cx - tw / 2, cyy - 18 + Double(i) * 14)
        }
        if let heads = spec.cabezaCm {
            var x = Config.safeLeft + dia + Config.gap + 20
            var y = cy + 10
            for cmv in [heads.0 + 0.3, heads.1] {
                let dd = Config.cm(cmv)
                ctx.setFillColor(CGColor(red: 244 / 255, green: 244 / 255, blue: 244 / 255, alpha: 1)!)
                ctx.setStrokeColor(gray)
                ctx.setLineWidth(2)
                ctx.beginPath()
                ctx.addEllipse(in: CGRect(x: x, y: y, width: dd, height: dd))
                ctx.drawPath(using: .fillStroke)
                drawText(ctx, "carita Ø \(cmv) cm", x + 4, y + 4, color: CGColor(red: 90 / 255, green: 90 / 255, blue: 90 / 255, alpha: 1))
                y += dd + Config.gap + 10
            }
            _ = x
        }
        return ctx.makeImage()
    }
}
