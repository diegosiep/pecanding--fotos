import Foundation
import CoreGraphics
import ImageIO

// Baja fotos de las ligas de Craft (WhatsForm / Google Drive), guarda subidas
// locales y detecta blanco y negro. Cache en Application Support/PecandingFotos/photos.
final class PhotoStore {
    static let shared = PhotoStore()

    let baseDir: URL
    let photosDir: URL
    let projectFile: URL
    let outDir: URL

    private init() {
        let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        baseDir = appSupport.appendingPathComponent("PecandingFotos", isDirectory: true)
        photosDir = baseDir.appendingPathComponent("photos", isDirectory: true)
        outDir = baseDir.appendingPathComponent("out", isDirectory: true)
        projectFile = baseDir.appendingPathComponent("project.json")
        try? FileManager.default.createDirectory(at: photosDir, withIntermediateDirectories: true)
        try? FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)
    }

    // MARK: - URLs

    static func driveId(_ url: String) -> String? {
        if let m = url.range(of: "drive.google.com/file/d/([^/]+)/", options: .regularExpression) {
            return String(url[m]).replacingOccurrences(of: "drive.google.com/file/d/", with: "").replacingOccurrences(of: "/", with: "")
        }
        if let m = url.range(of: "[?&]id=([^&]+)", options: .regularExpression) {
            let s = String(url[m])
            return s.components(separatedBy: "id=").last?.components(separatedBy: "&").first
        }
        return nil
    }

    static func candidateUrls(_ url: String) -> [String] {
        if let id = driveId(url) {
            return [
                "https://drive.usercontent.google.com/download?id=\(id)&export=download&confirm=t",
                "https://lh3.googleusercontent.com/d/\(id)=s0",
                "https://drive.google.com/uc?export=download&id=\(id)",
            ]
        }
        return [url]
    }

    private static let ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

    // MARK: - descarga

    func download(_ url: String) async -> PhotoRec {
        for cand in PhotoStore.candidateUrls(url) {
            var req = URLRequest(url: URL(string: cand)!)
            req.setValue(PhotoStore.ua, forHTTPHeaderField: "User-Agent")
            req.timeoutInterval = 30
            do {
                let (data, resp) = try await URLSession.shared.data(for: req)
                guard let http = resp as? HTTPURLResponse, http.statusCode == 200, data.count > 2000 else { continue }
                if let rec = saveData(data, originalUrl: url, suggestedName: cand) {
                    return rec
                }
            } catch {
                continue
            }
        }
        return PhotoRec(status: "sin_acceso", srcUrl: url)
    }

    func saveUpload(data: Data, filename: String) -> PhotoRec? {
        saveData(data, originalUrl: "local://" + filename, suggestedName: filename, status: "subida")
    }

    private func saveData(_ data: Data, originalUrl: String, suggestedName: String, status: String = "ok") -> PhotoRec? {
        guard let src = CGImageSourceCreateWithData(data as CFData, nil),
              let cg = CGImageSourceCreateImageAtIndex(src, 0, nil) else { return nil }
        let ext = (suggestedName as NSString).pathExtension.lowercased()
        let name = UUID().uuidString.prefix(16) + "." + (ext.isEmpty ? "img" : ext)
        let dest = photosDir.appendingPathComponent(String(name))
        do {
            try data.write(to: dest)
        } catch { return nil }
        return PhotoRec(status: status, path: "photos/\(name)", w: cg.width, h: cg.height, bn: PhotoStore.suggestBN(cg), srcUrl: originalUrl)
    }

    // MARK: - acceso

    func photoURL(_ rel: String) -> URL? {
        guard !rel.isEmpty else { return nil }
        return baseDir.appendingPathComponent(rel)
    }

    func cgImage(_ rel: String) -> CGImage? {
        guard let url = photoURL(rel), let src = CGImageSourceCreateWithURL(url as CFURL, nil) else { return nil }
        return CGImageSourceCreateImageAtIndex(src, 0, nil)
    }

    // Heurística B/N: saturación media baja en píxeles brillantes.
    static func suggestBN(_ cg: CGImage) -> Bool {
        let w = 128, h = max(1, Int(Double(cg.height) * 128.0 / Double(max(1, cg.width))))
        let cs = CGColorSpaceCreateDeviceRGB()
        guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w * 4, space: cs, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return false }
        ctx.draw(cg, in: CGRect(x: 0, y: 0, width: w, height: h))
        guard let d = ctx.data else { return false }
        let ptr = d.assumingMemoryBound(to: UInt8.self)
        var satSum = 0.0
        var count = 0
        for y in 0..<h {
            for x in 0..<w {
                let i = (y * w + x) * 4
                let r = Double(ptr[i]), g = Double(ptr[i + 1]), b = Double(ptr[i + 2])
                let mx = max(r, g, b), mn = min(r, g, b)
                if mx > 64 {
                    satSum += mx > 0 ? (mx - mn) / mx : 0
                    count += 1
                }
            }
        }
        guard count > 100 else { return false }
        return satSum / Double(count) < 0.08
    }
}
