import Foundation

// Medidas del equipo Pecanding (mismas que la app Python / skill Canva v5).
enum Config {
    static let pxPerCm = 37.7953
    static let sheetW = 945.0
    static let sheetH = 756.0
    static let sheetWcm = 25.0
    static let sheetHcm = 20.0

    static let guide = 2.0 * pxPerCm            // 75.6 px
    static let safeLeft = guide
    static let safeTop = guide
    static let safeRight = sheetW - guide       // 869.4
    static let safeBottom = sheetH - guide      // 680.4

    static let gap = 0.5 * pxPerCm              // separación para la tijera
    static let pageMinMargin = 10.0             // margen físico de la hoja

    static let labelFontPx = 12.0
    static let labelLineHeight = 1.15

    static let pdfDpi = 96.0                    // 945 px a 96 dpi = 25 cm exactos

    struct SizeSpec {
        let circleCm: Double
        let recortadaCm: (Double, Double)
        let gorritoCm: Double
        let cabezaCm: (Double, Double)?         // guirnalda de caritas
    }

    static let sizes: [String: SizeSpec] = [
        "Mini": .init(circleCm: 11.2, recortadaCm: (8.0, 9.0), gorritoCm: 8.0, cabezaCm: (4.3, 5.4)),
        "Mediano": .init(circleCm: 16.8, recortadaCm: (12.0, 12.5), gorritoCm: 11.5, cabezaCm: (8.5, 9.0)),
        "Grande": .init(circleCm: 17.6, recortadaCm: (13.0, 13.5), gorritoCm: 12.5, cabezaCm: nil),
        "Extra Grande": .init(circleCm: 18.8, recortadaCm: (14.5, 14.5), gorritoCm: 13.5, cabezaCm: nil),
    ]
    static let sizeOrder = ["Mini", "Mediano", "Grande", "Extra Grande"]

    static func cm(_ v: Double) -> Double { v * pxPerCm }

    static func recortadaDefaultCm(_ size: String, gorrito: Bool) -> Double {
        guard let s = sizes[size] else { return 12.25 }
        return gorrito ? s.gorritoCm : (s.recortadaCm.0 + s.recortadaCm.1) / 2
    }

    static func circlePx(_ size: String) -> Double { cm(sizes[size]?.circleCm ?? 16.8) }
}
