import Foundation

struct ImgBox: Codable, Equatable {
    var left: Double
    var top: Double
    var width: Double
    var height: Double
}

struct Order: Codable, Identifiable {
    var id: String = UUID().uuidString
    var num: String?
    var name: String = ""
    var response: String?
    var day: String = ""
    var size: String = ""
    var shape: String = "redondo"
    var mode: String? = nil            // "completa" | "recortada" | nil
    var gorrito: Bool = false
    var edibleLinks: [String] = []
    var refLinks: [String] = []
    var imageMissing: Bool = false
    var manual: Bool = false
    var needsReview: Bool = false
    var note: String = ""
    var status: String = "pendiente"  // pendiente | lista | hecha | excluida
    var statusReason: String = ""
    var bn: Bool = false

    enum CodingKeys: String, CodingKey {
        case id, num, name, response, day, size, shape, mode, gorrito, note, status, bn, manual
        case edibleLinks = "edible_links"
        case refLinks = "ref_links"
        case imageMissing = "image_missing"
        case needsReview = "needs_review"
        case statusReason = "status_reason"
    }

    var labelId: String {
        if let r = response { return "\(name) #\(r)" }
        return name
    }
}

struct Piece: Codable, Identifiable {
    var id: String = UUID().uuidString
    var orderId: String = ""
    var kind: String = "circle"        // circle (completa) | cutout (recortada)
    var size: String = "Mediano"
    var gorrito: Bool = false
    var bn: Bool = false
    var headOnly: Bool = false
    var day: String = ""
    var label: String = ""
    var photo: String = ""             // ruta relativa en photos/
    var photoStatus: String = "pendiente"
    var imgBox: ImgBox? = nil
    var hasMask: Bool = false
    var x: Double = 0
    var y: Double = 0
    var w: Double = 0
    var h: Double = 0
    var rotation: Double = 0
    var sheetId: String = ""
    var pending: Bool = false

    enum CodingKeys: String, CodingKey {
        case id, kind, size, gorrito, bn, day, label, photo, x, y, w, h, rotation, pending, hasMask = "has_mask"
        case orderId = "order_id"
        case headOnly = "head_only"
        case photoStatus = "photo_status"
        case imgBox = "img_box"
        case sheetId = "sheet_id"
    }

    var effW: Double {
        let r = abs(rotation.truncatingRemainder(dividingBy: 180))
        return (r > 45 && r < 135) ? h : w
    }
    var effH: Double {
        let r = abs(rotation.truncatingRemainder(dividingBy: 180))
        return (r > 45 && r < 135) ? w : h
    }
}

struct Sheet: Codable, Identifiable {
    var id: String = UUID().uuidString
    var title: String = "hoja"
    var kind: String = "hoja"           // hoja | guia
    var size: String = ""
}

struct PhotoRec: Codable {
    var status: String = "sin_acceso"  // ok | subida | sin_acceso
    var path: String = ""
    var w: Int = 0
    var h: Int = 0
    var bn: Bool = false
    var srcUrl: String = ""

    enum CodingKeys: String, CodingKey {
        case status, path, w, h, bn
        case srcUrl = "src_url"
    }
}

struct Project: Codable {
    var week: String = ""
    var sourceName: String = ""
    var orders: [Order] = []
    var pieces: [Piece] = []
    var sheets: [Sheet] = []
    var photos: [String: PhotoRec] = [:]

    enum CodingKeys: String, CodingKey {
        case week
        case sourceName = "source_name"
        case orders, pieces, sheets, photos
    }
}

func newPieceForOrder(_ o: Order, photo: String?, photoStatus: String, index: Int = 0, total: Int = 1) -> Piece {
    let size = o.size.isEmpty ? "Mediano" : o.size
    let mode = o.mode ?? "recortada"
    var p = Piece()
    p.orderId = o.id
    p.size = size
    p.day = o.day
    p.gorrito = o.gorrito
    p.bn = o.bn
    p.kind = (mode == "completa") ? "circle" : "cutout"
    p.photo = photo ?? ""
    p.photoStatus = photoStatus
    p.pending = !(photoStatus == "ok" || photoStatus == "subida")
    let suffix = total > 1 ? " · pastel \(index + 1) de \(total)" : ""
    if p.kind == "circle" {
        let d = Config.circlePx(size)
        p.w = d
        p.h = d
    } else {
        p.h = Config.cm(Config.recortadaDefaultCm(size, gorrito: p.gorrito))
        p.w = p.h
    }
    var flags: [String] = []
    if p.gorrito { flags.append("GORRITO") }
    if p.bn { flags.append("B/N") }
    let base = "\(size.uppercased()) \(p.kind == "circle" ? "COMPLETA" : "RECORTADA")"
    let head = flags.isEmpty ? "\(base) · \(p.day)" : "\(base) · \(flags.joined(separator: " · ")) · \(p.day)"
    p.label = "\(head)\(suffix)\n\(o.labelId)"
    return p
}
