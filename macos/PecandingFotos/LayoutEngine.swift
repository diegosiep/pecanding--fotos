import Foundation

// Acomodo compacto (mismo algoritmo que la app Python): skyline bottom-left con
// gap ≥ 0.5 cm, zona segura 21×16 cm desde (75.6, 75.6), círculos grandes pegados
// arriba-izquierda (pueden sobresalir abajo, nunca fuera de la hoja).
enum LayoutEngine {

    static let dayOrder = ["Lunes", "Martes", "Miércoles", "Miercoles", "Jueves", "Viernes", "Sábado", "Sabado", "Domingo"]

    static func bottomLimit(_ p: Piece) -> Double {
        if p.kind == "circle", max(p.effW, p.effH) > (Config.safeBottom - Config.safeTop) {
            return Config.sheetH - Config.pageMinMargin
        }
        return Config.safeBottom
    }

    static func topFor(_ p: Piece) -> Double {
        if p.kind == "circle" {
            return min(Config.safeTop, bottomLimit(p) - max(p.effW, p.effH))
        }
        return Config.safeTop
    }

    static func collides(_ x: Double, _ y: Double, _ w: Double, _ h: Double, _ placed: [(Double, Double, Double, Double)], _ gap: Double) -> Bool {
        for q in placed {
            if x < q.0 + q.2 + gap, x + w + gap > q.0, y < q.1 + q.3 + gap, y + h + gap > q.1 {
                return true
            }
        }
        return false
    }

    /// Devuelve hojas (listas de piezas con x/y asignadas).
    static func packIntoSheets(_ pieces: [Piece]) -> [[Piece]] {
        let gap = Config.gap
        let left = Config.safeLeft, right = Config.safeRight
        var sheets: [[Piece]] = []
        var placed: [(Double, Double, Double, Double)] = []
        var skyline: [(x: Double, y: Double, w: Double)] = [(left, Config.safeTop, right - left)]

        func profile(_ x0: Double, _ x1: Double) -> Double {
            var y = Config.safeTop
            for s in skyline where s.x < x1, s.x + s.w > x0 {
                y = max(y, s.y)
            }
            return y
        }

        func updateSkyline(_ x: Double, _ y: Double, _ w: Double, _ h: Double) {
            let top = y + h
            var new: [(Double, Double, Double)] = []
            for s in skyline {
                let xe = s.x + s.w
                if xe <= x || s.x >= x + w {
                    new.append((s.x, s.y, s.w))
                } else {
                    if s.x < x { new.append((s.x, s.y, x - s.x)) }
                    new.append((max(s.x, x), top, min(xe, x + w) - max(s.x, x)))
                    if xe > x + w { new.append((x + w, s.y, xe - (x + w))) }
                }
            }
            new.sort { $0.0 < $1.0 }
            var merged: [(Double, Double, Double)] = []
            for seg in new {
                if let last = merged.last, abs(last.1 - seg.1) < 0.5, abs(last.0 + last.2 - seg.0) < 0.5 {
                    merged[merged.count - 1].2 += seg.2
                } else {
                    merged.append(seg)
                }
            }
            skyline = merged
        }

        func place(_ p: inout Piece) -> Bool {
            let w = p.effW, h = p.effH
            let bl = bottomLimit(p)
            let topMin = topFor(p)
            var cands: Set<Double> = [left]
            for s in skyline { cands.insert(s.x) }
            for q in placed { cands.insert(q.0 + q.2 + gap) }
            var best: (x: Double, y: Double)? = nil
            for x in cands.sorted() {
                if x + w > right + 0.5 { continue }
                let y = max(profile(x, x + w), topMin)
                if y + h > bl + 0.5 { continue }
                if collides(x, y, w, h, placed, gap) { continue }
                if best == nil || (y, x) < (best!.y, best!.x) { best = (x, y) }
            }
            guard let b = best else { return false }
            p.x = b.x
            p.y = b.y
            placed.append((b.x, b.y, w, h))
            updateSkyline(b.x, b.y, w, h)
            return true
        }

        var input = pieces
        for i in input.indices {
            if !sheets.isEmpty, place(&input[i]) {
                sheets[sheets.count - 1].append(input[i])
                continue
            }
            sheets.append([])
            placed = []
            skyline = [(left, Config.safeTop, right - left)]
            if !place(&input[i]) {
                let w = input[i].effW, h = input[i].effH
                input[i].x = Config.safeLeft
                input[i].y = min(Config.safeTop, Config.sheetH - Config.pageMinMargin - h)
                placed.append((input[i].x, input[i].y, w, h))
                updateSkyline(input[i].x, input[i].y, w, h)
            }
            sheets[sheets.count - 1].append(input[i])
        }
        return sheets
    }

    static func dayKey(_ p: Piece) -> (Int, String, String) {
        let d = (p.day.split(separator: " ").first ?? "").capitalized
        let di = dayOrder.firstIndex(of: d) ?? 99
        return (di, p.day, p.label)
    }

    /// Reconstruye hojas GUÍA + acomodo por tamaño. Devuelve resumen para mostrar.
    @discardableResult
    static func autoLayout(_ project: inout Project) -> [String: Any] {
        var pieces = project.pieces.filter { !$0.pending }
        for i in pieces.indices { pieces[i].rotation = 0 }
        project.sheets = []
        var bySize: [String: [Piece]] = [:]
        for p in pieces { bySize[p.size, default: []].append(p) }
        var summary: [String: Any] = ["sizes": [:], "guias": 0, "hojas": 0]
        var sizesSummary: [String: Int] = [:]
        for size in Config.sizeOrder {
            guard var group = bySize[size], !group.isEmpty else { continue }
            group.sort { dayKey($0) < dayKey($1) }
            let g = Sheet(title: "GUÍA \(size.uppercased())", kind: "guia", size: size)
            project.sheets.append(g)
            summary["guias"] = (summary["guias"] as? Int ?? 0) + 1
            for (i, hoja) in packIntoSheets(group).enumerated() {
                let s = Sheet(title: "\(size) · hoja \(i + 1)", kind: "hoja", size: size)
                project.sheets.append(s)
                for var p in hoja {
                    p.sheetId = s.id
                    if let idx = project.pieces.firstIndex(where: { $0.id == p.id }) {
                        project.pieces[idx].x = p.x
                        project.pieces[idx].y = p.y
                        project.pieces[idx].rotation = 0
                        project.pieces[idx].sheetId = s.id
                    }
                }
                summary["hojas"] = (summary["hojas"] as? Int ?? 0) + 1
            }
            sizesSummary[size] = group.count
        }
        summary["sizes"] = sizesSummary
        for i in project.pieces.indices where project.pieces[i].pending {
            project.pieces[i].sheetId = ""
        }
        return summary
    }

    /// Verificación: cajas dentro de zona (salvo círculos grandes por abajo), gaps, hoja.
    static func checkLayout(_ project: Project) -> [String] {
        var problems: [String] = []
        let gapMin = 0.4 * Config.pxPerCm
        var bySheet: [String: [Piece]] = [:]
        for p in project.pieces where !p.sheetId.isEmpty {
            bySheet[p.sheetId, default: []].append(p)
        }
        for (_, ps) in bySheet {
            for p in ps {
                let bigCircle = p.kind == "circle" && p.effH > (Config.safeBottom - Config.safeTop)
                if p.x < Config.safeLeft - 0.5, !bigCircle {
                    problems.append("\(p.id): inicia antes de la guía izquierda (x=\(Int(p.x)))")
                }
                if p.y < Config.safeTop - 0.5, !bigCircle {
                    problems.append("\(p.id): inicia antes de la guía de arriba (y=\(Int(p.y)))")
                }
                if p.x + p.effW > Config.sheetW + 0.5 || p.y + p.effH > Config.sheetH + 0.5 {
                    problems.append("\(p.id): sale de la hoja")
                }
                if p.x + p.effW > Config.safeRight + 0.5 {
                    problems.append("\(p.id): cruza la zona segura derecha")
                }
                if p.y + p.effH > Config.safeBottom + 0.5, !bigCircle {
                    problems.append("\(p.id): cruza la zona segura inferior")
                }
            }
            for i in 0..<ps.count {
                for j in (i + 1)..<ps.count {
                    let a = ps[i], b = ps[j]
                    let ox = min(a.x + a.effW, b.x + b.effW) - max(a.x, b.x)
                    let oy = min(a.y + a.effH, b.y + b.effH) - max(a.y, b.y)
                    if ox > 0, oy > 0 {
                        problems.append("se enciman \(a.id) y \(b.id)")
                    } else if ox > -gapMin, oy > -gapMin, ox <= 0, oy <= 0 {
                        problems.append("gap < 0.4 cm entre \(a.id) y \(b.id)")
                    }
                }
            }
        }
        return problems
    }
}
