import Foundation
import CoreGraphics
import CoreImage
import Vision

// Quita el fondo con Vision (segmentación de persona) — equivalente nativo a rembg.
// Devuelve la máscara y las cajas del sujeto / cabeza en px de la imagen original.
enum VisionCutout {

    struct MaskResult {
        var pixelBuffer: CVPixelBuffer?
        var subject: CGRect?   // (x, y, w, h) en px de imagen
        var head: CGRect?
    }

    static func analyze(_ cg: CGImage) -> MaskResult {
        let request = VNGeneratePersonSegmentationRequest()
        request.qualityLevel = .balanced
        let handler = VNImageRequestHandler(cgImage: cg, options: [:])
        do {
            try handler.perform([request])
        } catch {
            return MaskResult()
        }
        guard let result = request.results?.first, let mask = result.pixelBuffer else {
            return MaskResult()
        }
        let w = CVPixelBufferGetWidth(mask)
        let h = CVPixelBufferGetHeight(mask)
        CVPixelBufferLockBaseAddress(mask, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(mask, .readOnly) }
        guard let base = CVPixelBufferGetBaseAddress(mask) else { return MaskResult(pixelBuffer: mask) }
        let bytesPerRow = CVPixelBufferGetBytesPerRow(mask)
        let buf = base.assumingMemoryBound(to: UInt8.self)

        func value(_ x: Int, _ y: Int) -> Int {
            Int(buf[y * bytesPerRow + x])
        }
        // caja del sujeto
        var minX = w, minY = h, maxX = -1, maxY = -1
        var rowWidth = [Int](repeating: 0, count: h)
        for y in 0..<h {
            for x in 0..<w {
                if value(x, y) > 40 {
                    rowWidth[y] += 1
                    if x < minX { minX = x }
                    if x > maxX { maxX = x }
                    if y < minY { minY = y }
                    if y > maxY { maxY = y }
                }
            }
        }
        let subject: CGRect? = (maxX >= 0) ? CGRect(x: minX, y: minY, width: maxX - minX + 1, height: maxY - minY + 1) : nil
        // caja de la cabeza: franja superior donde el ancho se angosta bajo los hombros
        var head: CGRect?
        if let s = subject {
            let bodyMax = rowWidth[Int(Double(h) * 0.4)..<h].max() ?? 0
            if bodyMax > 0 {
                let limit = 0.6 * Double(bodyMax)
                var run = 0
                var headEnd = minY + max(1, Int(Double(h) * 0.12))
                let yLimit = min(maxY + 1, minY + Int(Double(h) * 0.7))
                for y in minY..<yLimit {
                    if Double(rowWidth[y]) < limit {
                        run += 1
                        if run >= 5 { headEnd = max(minY + 1, y - 4); break }
                    } else {
                        run = 0
                        headEnd = y + 1
                    }
                }
                headEnd = max(headEnd, minY + 1)
                // ancho de la fila headEnd-1
                var hx0 = w, hx1 = -1
                let hy = min(headEnd - 1, h - 1)
                for x in 0..<w where value(x, hy) > 40 {
                    if x < hx0 { hx0 = x }
                    if x > hx1 { hx1 = x }
                }
                if hx1 >= hx0 {
                    head = CGRect(x: hx0, y: minY, width: hx1 - hx0 + 1, height: headEnd - minY)
                } else {
                    head = CGRect(x: s.minX, y: s.minY, width: s.width, height: headEnd - minY)
                }
            }
        }
        return MaskResult(pixelBuffer: mask, subject: subject, head: head)
    }

    /// Aplica la máscara de persona a la imagen → CGImage RGBA con alfa 0 en el fondo.
    static func applyMask(_ cg: CGImage, _ mask: CVPixelBuffer) -> CGImage? {
        let w = cg.width, h = cg.height
        guard CVPixelBufferGetWidth(mask) == w, CVPixelBufferGetHeight(mask) == h else { return nil }
        let cs = CGColorSpaceCreateDeviceRGB()
        guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w * 4, space: cs, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return nil }
        ctx.draw(cg, in: CGRect(x: 0, y: 0, width: w, height: h))
        guard let out = ctx.data else { return nil }
        let dst = out.assumingMemoryBound(to: UInt8.self)
        CVPixelBufferLockBaseAddress(mask, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(mask, .readOnly) }
        guard let base = CVPixelBufferGetBaseAddress(mask) else { return nil }
        let bytesPerRow = CVPixelBufferGetBytesPerRow(mask)
        let m = base.assumingMemoryBound(to: UInt8.self)
        for y in 0..<h {
            for x in 0..<w {
                let a = m[y * bytesPerRow + x] > 40 ? 255 : 0
                let i = (y * w + x) * 4
                dst[i + 3] = UInt8(a)
            }
        }
        return ctx.makeImage()
    }

    /// Cutout completo: analiza y aplica. Devuelve imagen RGBA recortada (con alfa) o nil.
    static func cutout(_ cg: CGImage) -> CGImage? {
        let r = analyze(cg)
        guard let mask = r.pixelBuffer else { return nil }
        return applyMask(cg, mask)
    }
}
