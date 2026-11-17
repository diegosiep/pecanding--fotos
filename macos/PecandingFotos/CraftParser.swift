import Foundation

// Parser de la página semanal de PEDIDOS PECANDING (mismo formato que la app Python).
enum CraftParser {

    static let months: [String: Int] = [
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
        "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
        "noviembre": 11, "diciembre": 12,
    ]

    static func rx(_ pattern: String, _ opts: NSRegularExpression.Options = []) -> NSRegularExpression {
        // swiftlint:disable:next force_try
        try! NSRegularExpression(pattern: pattern, options: opts)
    }

    static func match(_ re: NSRegularExpression, _ s: String) -> [String]? {
        guard let m = re.matches(in: s, range: NSRange(s.startIndex..., in: s)).first else { return nil }
        return (0..<m.numberOfRanges).map { i -> String in
            guard let r = Range(m.range(at: i), in: s) else { return "" }
            return String(s[r])
        }
    }

    // MARK: - semanas

    static func parseWeekTitle(_ title: String) -> (start: Date, end: Date)? {
        let t = title.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
        let cal = Calendar(identifier: .gregorian)
        func comps(_ y: Int, _ m: Int, _ d: Int) -> DateComponents { DateComponents(year: y, month: m, day: d) }
        let r1 = rx("(\\d{1,2})\\s+al\\s+(\\d{1,2})\\s+de\\s+(\\w+)\\s+de\\s+(\\d{4})")
        if let m = match(r1, t) {
            if let mon = months[m[3]], let y = Int(m[4]), let d1 = Int(m[1]), let d2 = Int(m[2]) {
                guard let s = cal.date(from: comps(y, mon, d1)), let e = cal.date(from: comps(y, mon, d2)) else { return nil }
                return (s, e)
            }
        }
        let r2 = rx("(\\d{1,2})\\s+de\\s+(\\w+)\\s+al\\s+(\\d{1,2})\\s+de\\s+(\\w+)\\s+de\\s+(\\d{4})")
        if let m = match(r2, t) {
            if let m1 = months[m[2]], let m2 = months[m[4]], let y = Int(m[5]), let d1 = Int(m[1]), let d2 = Int(m[3]) {
                guard let s = cal.date(from: comps(y, m1, d1)), let e = cal.date(from: comps(y, m2, d2)) else { return nil }
                return (s, e)
            }
        }
        return nil
    }

    /// Semana en curso (regla: lunes–domingo; en domingo, la que empieza mañana).
    static func currentWeekTitle(_ titles: [String], today: Date = Date()) -> String? {
        var t = today
        let cal = Calendar.current
        if cal.component(.weekday, from: t) == 1 { // domingo
            t = cal.date(byAdding: .day, value: 1, to: t) ?? t
        }
        var best: String?
        for title in titles {
            guard let b = parseWeekTitle(title) else { continue }
            if b.start <= t && t <= b.end { return title }
            if b.start > t, best == nil || (parseWeekTitle(best!)?.start ?? .distantFuture) > b.start { best = title }
        }
        return best
    }

    // MARK: - página semanal

    struct WeekPage {
        var title: String
        var orders: [Order]
        var notes: [String]
    }

    /// Soporta una página (blocks get) o el documento raíz con sub-páginas.
    static func parseCraftMarkdown(_ text: String) -> [String: WeekPage] {
        var pages: [String: WeekPage] = [:]
        let pageRe = rx("<page id=\"[^\"]*\">")
        var chunks: [String] = []
        var last = text.startIndex
        for m in pageRe.matches(in: text, range: NSRange(text.startIndex..., in: text)) {
            if let r = Range(m.range, in: text) {
                chunks.append(String(text[last..<r.lowerBound]))
                last = r.upperBound
            }
        }
        chunks.append(String(text[last...]))
        let titleRe = rx("<pageTitle>(.*?)</pageTitle>", [.dotMatchesLineSeparators])
        for chunk in chunks {
            guard let tm = match(titleRe, chunk), let title = tm[safe: 1]?.trimmingCharacters(in: .whitespacesAndNewlines), !title.isEmpty, pages[title] == nil else { continue }
            let p = parseWeekPage(title: title, markdown: chunk)
            pages[title] = p
        }
        if pages.isEmpty {
            pages["semana"] = parseWeekPage(title: "semana", markdown: text)
        }
        return pages
    }

    static func parseWeekPage(title: String, markdown: String) -> WeekPage {
        var body = markdown
        for pat in ["</?page[^>]*>", "</?pageTitle>", "</?content>", "<page id=\"[^\"]*\">"] {
            body = body.replacingOccurrences(of: pat, with: "", options: .regularExpression)
        }
        var orders: [Order] = []
        var notes: [String] = []
        var day = ""
        var current: (num: String?, head: String, lines: [String], formal: Bool)? = nil

        func flush() {
            guard let c = current else { return }
            if let o = parseEntry(num: c.num, head: c.head, lines: c.lines, day: day.isEmpty ? nil : day, formal: c.formal) {
                if !o.name.isEmpty || o.mode != nil || !o.edibleLinks.isEmpty {
                    orders.append(o)
                }
            }
            current = nil
        }

        for block in splitBlocks(body) {
            let first = block[0]
            if let hm = match(rx("^#{1,6}\\s*(.*)$"), first) {
                flush()
                day = dayFromHeading(hm[1])
                continue
            }
            if let nm = match(rx("^\\s*\\*{0,2}\\s*(\\d{1,3})\\.\\s*(.*)$"), first) {
                flush()
                let formal = first.trimmingCharacters(in: .whitespaces).hasPrefix("**")
                current = (nm[1], nm[2].trimmingCharacters(in: .whitespaces), Array(block.dropFirst()), formal)
                continue
            }
            if let c = current, !c.formal {
                current?.lines.append(contentsOf: block)
            } else {
                let txt = block.joined(separator: " ")
                if txt.lowercased().contains("foto comestible"), txt.contains("[foto comestible](") {
                    flush()
                    current = (nil, txt, [], false)
                } else {
                    notes.append(txt)
                }
            }
        }
        flush()
        return WeekPage(title: title.trimmingCharacters(in: .whitespaces), orders: orders, notes: notes)
    }

    static func splitBlocks(_ text: String) -> [[String]] {
        var blocks: [[String]] = []
        var cur: [String] = []
        for line in text.split(separator: "\n", omittingEmptySubsequences: false) {
            if line.trimmingCharacters(in: .whitespaces).isEmpty {
                if !cur.isEmpty { blocks.append(cur); cur = [] }
            } else {
                cur.append(String(line))
            }
        }
        if !cur.isEmpty { blocks.append(cur) }
        return blocks
    }

    static func dayFromHeading(_ h: String) -> String {
        if let m = match(rx("\\b(lunes|martes|mi[eé]rcoles|jueves|viernes|s[áa]bado|domingo)\\s+(\\d{1,2})\\b", [.caseInsensitive]), h.lowercased()) {
            return "\(m[1].prefix(1).uppercased() + m[1].dropFirst()) \(m[2])"
        }
        return h.trimmingCharacters(in: .whitespaces)
    }

    static func dayFromText(_ text: String, fallback: String) -> String {
        if let m = match(rx("entrega:\\s*([^;.]+)", [.caseInsensitive]), text), !m[1].isEmpty {
            let d = dayFromHeading(m[1])
            if !d.isEmpty { return d }
        }
        if let m = match(rx("\\b(lunes|martes|mi[eé]rcoles|jueves|viernes|s[áa]bado|domingo)\\s+(\\d{1,2})\\b", [.caseInsensitive]), text.lowercased()) {
            return "\(m[1].prefix(1).uppercased() + m[1].dropFirst()) \(m[2])"
        }
        return fallback
    }

    static func links(_ text: String) -> (edible: [String], ref: [String]) {
        let re = rx("\\[([^\\]]+)\\]\\((https?://[^)\\s]+)\\)")
        var edible: [(String, String)] = []
        var ref: [String] = []
        for m in re.matches(in: text, range: NSRange(text.startIndex..., in: text)) {
            guard let lr = Range(m.range(at: 1), in: text), let ur = Range(m.range(at: 2), in: text) else { continue }
            let label = String(text[lr]).lowercased()
            let url = String(text[ur])
            if label.hasPrefix("foto comestible") { edible.append((label, url)) }
            else if label.contains("referencia") { ref.append(url) }
        }
        edible.sort { $0.0 < $1.0 }
        return (edible.map { $0.1 }, ref)
    }

    static func parseEntry(num: String?, head: String, lines: [String], day: String?, formal: Bool) -> Order? {
        let headFull = head
        var o = Order(num: num, day: day ?? "", manual: !formal)
        var rest = ""
        if let m = match(rx("^(.*?)\\s*\\(#([0-9]{4,6}(?:-\\d+)?)\\)\\s*(?:—|-)\\s*(.*)$"), headFull),
           m.count > 3, !m[2].isEmpty {
            o.name = m[1].trimmingCharacters(in: CharacterSet(charactersIn: " *-"))
            o.response = m[2]
            rest = m[3]
        } else {
            o.name = headFull.trimmingCharacters(in: CharacterSet(charactersIn: " *-"))
        }
        let full = ([rest] + lines).filter { !$0.isEmpty }.joined(separator: " ")
        // tamaño en los primeros campos
        let fields = formal ? full.components(separatedBy: ";") : [full]
        let sizeRe = rx("(extra\\s*grande|grande|mediano|mini)", [.caseInsensitive])
        for f in fields.prefix(4) {
            if let sm = match(sizeRe, f) {
                o.size = normalizeSize(sm[1])
                break
            }
        }
        if o.size.isEmpty, let sm = match(sizeRe, full) {
            o.size = normalizeSize(sm[1])
        }
        let firstField = formal ? (fields.first ?? "") : full
        if rx("coraz[oó]n|rectangular|cuadrado|forma de", [.caseInsensitive]).matches(in: full, range: NSRange(full.startIndex..., in: full)).count > 0,
           rx("\\bredondo\\b", [.caseInsensitive]).matches(in: firstField, range: NSRange(firstField.startIndex..., in: firstField)).isEmpty {
            o.shape = "otro"
        }
        let low = full.lowercased()
        if low.contains("sin foto comestible") {
            o.mode = nil
        } else if rx("foto comestible\\s*recortada|fotito\\s*cake", [.caseInsensitive]).matches(in: low, range: NSRange(low.startIndex..., in: low)).count > 0 {
            o.mode = "recortada"
        } else if rx("foto comestible\\s*completa", [.caseInsensitive]).matches(in: low, range: NSRange(low.startIndex..., in: low)).count > 0 {
            o.mode = "completa"
        } else if low.contains("foto comestible") {
            o.mode = "recortada"
            o.needsReview = true
            o.note = "modo no explícito; se tomó recortada (fotito cake) — revisar"
        }
        for field in full.components(separatedBy: ";") {
            let fl = field.lowercased()
            if fl.contains("foto comestible"), !fl.contains("sin foto"), fl.contains("gorrito") {
                o.gorrito = true
            }
        }
        if !formal, low.contains("foto comestible"), low.contains("gorrito") {
            o.gorrito = true
        }
        if low.contains("no trae la imagen") || low.contains("no trae las im") {
            o.imageMissing = true
        }
        let (ed, rf) = links([head, full].joined(separator: " "))
        o.edibleLinks = ed
        o.refLinks = rf
        o.day = dayFromText(full, fallback: day ?? "")
        return o
    }

    static func normalizeSize(_ raw: String) -> String {
        let s = raw.lowercased().replacingOccurrences(of: "\\s+", with: " ", options: .regularExpression)
        if s.contains("extra") && s.contains("grande") { return "Extra Grande" }
        if s.contains("grande") { return "Grande" }
        if s.contains("mediano") || s.contains("mediana") { return "Mediano" }
        if s.contains("mini") { return "Mini" }
        return ""
    }
}

extension Array {
    subscript(safe index: Int) -> Element? {
        indices.contains(index) ? self[index] : nil
    }
}
