import Foundation
import AppKit

// Lienzo de la hoja 945×756: dibuja el render del servidor (mismo que Python),
// y permite mover, cambiar tamaño (manija SE), rotar y ajustar el encuadre (img_box).
struct SheetCanvasView: NSViewRepresentable {
    @ObservedObject var store: ProjectStore

    func makeNSView(context: Context) -> CanvasView {
        let v = CanvasView()
        v.store = store
        return v
    }

    func updateNSView(_ nsView: CanvasView, context: Context) {
        nsView.store = store
        nsView.setNeedsDisplay(nsView.bounds)
    }
}

final class CanvasView: NSView {
    var store: ProjectStore?
    private var drag: (kind: String, id: String, ox: Double, oy: Double, ib: ImgBox?)?
    private var scale: Double = 1

    override var isFlipped: Bool { true }

    private func toSheet(_ e: NSEvent) -> CGPoint {
        let p = convert(e.locationInWindow, from: nil)
        return CGPoint(x: p.x / scale, y: p.y / scale)
    }

    private func pieces() -> [Piece] {
        guard let sid = store?.selectedSheetId else { return [] }
        return store?.project.pieces.filter { $0.sheetId == sid } ?? []
    }

    private func hit(_ x: Double, _ y: Double) -> Piece? {
        for p in pieces().reversed() {
            if x >= p.x, x <= p.x + p.effW, y >= p.y, y <= p.y + p.effH { return p }
        }
        return nil
    }

    private func isResizeHandle(_ p: Piece, _ x: Double, _ y: Double) -> Bool {
        x >= p.x + p.effW - 10 && x <= p.x + p.effW + 2 && y >= p.y + p.effH - 10 && y <= p.y + p.effH + 2
    }

    override func draw(_ dirtyRect: CGRect) {
        guard let store = store, let sid = store.selectedSheetId,
              let sheet = store.project.sheets.first(where: { $0.id == sid }),
              let cg = SheetRenderer.renderCGImage(store.project, sheet, guides: true) else {
            NSColor.white.setFill()
            NSRectFill(bounds)
            return
        }
        let img = NSImage(cgImage: cg, size: NSSize(width: Config.sheetW, height: Config.sheetH))
        scale = min(bounds.width / Config.sheetW, bounds.height / Config.sheetH)
        if scale <= 0 { scale = 1 }
        let dw = Config.sheetW * scale, dh = Config.sheetH * scale
        let dx = (bounds.width - dw) / 2, dy = (bounds.height - dh) / 2
        NSColor.white.setFill()
        NSRectFill(bounds)
        img.draw(in: NSRect(x: dx, y: dy, width: dw, height: dh), from: .zero, operation: .copy, fraction: 1)
        // selección
        if let sel = store.selectedPieceId, let p = store.project.pieces.first(where: { $0.id == sel }), p.sheetId == sid {
            let r = NSRect(x: dx + p.x * scale, y: dy + p.y * scale, width: p.effW * scale, height: p.effH * scale)
            NSColor.systemRed.setStroke()
            NSBezierPath(rect: r).stroke()
            let h = NSRect(x: r.maxX - 6, y: r.maxY - 6, width: 12, height: 12)
            NSColor.systemRed.setFill()
            NSRectFill(h)
        }
    }

    override func mouseDown(with e: NSEvent) {
        guard let store = store else { return }
        let p = toSheet(e)
        if let hit = hit(p.x, p.y) {
            store.selectedPieceId = hit.id
            if isResizeHandle(hit, p.x, p.y) {
                drag = ("resize", hit.id, p.x, p.y, nil)
            } else if store.encuadreMode, !hit.photo.isEmpty, let ib = hit.imgBox ?? SheetRenderer.imgBox(hit, PhotoStore.shared.cgImage(hit.photo) ?? CGImage.empty1x1) {
                drag = ("frame", hit.id, p.x, p.y, ib)
            } else {
                drag = ("move", hit.id, p.x - hit.x, p.y - hit.y, nil)
            }
        } else {
            store.selectedPieceId = nil
        }
        setNeedsDisplay(bounds)
    }

    override func mouseDragged(with e: NSEvent) {
        guard let store = store, var d = drag, let p = store.project.pieces.first(where: { $0.id == d.id }) else { return }
        let m = toSheet(e)
        switch d.kind {
        case "move":
            store.updatePiece(d.id) { piece in
                piece.x = max(0, min(Config.sheetW - piece.w, m.x - d.ox))
                piece.y = max(0, min(Config.sheetH - piece.h, m.y - d.oy))
            }
        case "resize":
            store.updatePiece(d.id) { piece in
                let nw = max(30, m.x - piece.x), nh = max(30, m.y - piece.y)
                if piece.kind == "circle" { let dd = max(nw, nh); piece.w = dd; piece.h = dd }
                else { piece.w = nw; piece.h = nh }
            }
        case "frame":
            if var ib = d.ib {
                let W = Double(PhotoStore.shared.cgImage(p.photo)?.width ?? 1)
                let H = Double(PhotoStore.shared.cgImage(p.photo)?.height ?? 1)
                ib.left = max(0, min(W - ib.width, ib.left + (d.ox - m.x) * (ib.width / max(1, p.w))))
                ib.top = max(0, min(H - ib.height, ib.top + (d.oy - m.y) * (ib.height / max(1, p.h))))
                store.updatePiece(d.id) { $0.imgBox = ib }
                d.ib = ib
                drag = d
            }
        default: break
        }
        setNeedsDisplay(bounds)
    }

    override func mouseUp(with e: NSEvent) {
        drag = nil
        store?.save()
        store?.bump()
    }

    override func scrollWheel(with e: NSEvent) {
        guard let store = store, store.encuadreMode, let sel = store.selectedPieceId else { return }
        let p = store.project.pieces.first(where: { $0.id == sel })
        guard var ib = p?.imgBox, ib.width > 0 else { return }
        let f = e.deltaY < 0 ? 1.1 : 1.0 / 1.1
        let W = Double(PhotoStore.shared.cgImage(p?.photo ?? "")?.width ?? 1)
        let H = Double(PhotoStore.shared.cgImage(p?.photo ?? "")?.height ?? 1)
        let cx = ib.left + ib.width / 2, cy = ib.top + ib.height / 2
        ib.width = max(20, ib.width * f)
        ib.height = max(20, ib.height * f)
        ib.left = max(0, cx - ib.width / 2)
        ib.top = max(0, cy - ib.height / 2)
        ib.left = min(ib.left, max(0, W - ib.width))
        ib.top = min(ib.top, max(0, H - ib.height))
        store.updatePiece(sel) { $0.imgBox = ib }
        setNeedsDisplay(bounds)
    }
}

extension CGImage {
    static var empty1x1: CGImage {
        let cs = CGColorSpaceCreateDeviceRGB()
        let ctx = CGContext(data: nil, width: 1, height: 1, bitsPerComponent: 8, bytesPerRow: 4, space: cs, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
        return ctx.makeImage()!
    }
}
