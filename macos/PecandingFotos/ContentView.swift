import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @EnvironmentObject var store: ProjectStore
    @State private var showImport = false
    @State private var importText = ""
    @State private var importSource = "pegado"
    @State private var weekChoice: String? = nil
    @State private var availableWeeks: [String] = []
    @State private var fetchOnPrepare = true
    @State private var importError: String?
    @State private var showExport = false
    @State private var exportMessage = ""
    @State private var showFilePicker = false

    var body: some View {
        NavigationSplitView {
            ordersSidebar
        } content: {
            editorPane
        } detail: {
            inspector
        }
        .navigationSplitViewColumnWidth(min: 260, ideal: 300, max: 380)
        .toolbar {
            ToolbarItemGroup {
                Button("Importar Craft…") { showImport = true }
                Toggle("bajar fotos", isOn: $fetchOnPrepare).toggleStyle(.checkbox)
                Button("Preparar semana") {
                    Task { await store.prepare(fetch: fetchOnPrepare) }
                }
                Button("Auto acomodar") { store.autoLayout() }
                Button("+ hoja") { store.addSheet(title: "hoja nueva") }
                Button("Exportar PDF") {
                    let (path, problems) = store.export()
                    exportMessage = path + (problems.isEmpty ? "" : "\n\nPROBLEMAS:\n" + problems.joined(separator: "\n"))
                    showExport = true
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .sheet(isPresented: $showImport) { importSheet }
        .alert("Exportación", isPresented: $showExport) {
            Button("OK") {}
        } message: { Text(exportMessage) }
        .fileImporter(isPresented: $showFilePicker, allowedContentTypes: [.plainText, .json, .data]) { res in
            if case .success(let url) = res, let text = try? String(contentsOf: url, encoding: .utf8) {
                importSource = url.lastPathComponent
                importText = text
                showImport = true
            }
        }
        .onAppear {
            if store.project.sheets.isEmpty { store.selectedSheetId = nil }
            else if store.selectedSheetId == nil { store.selectedSheetId = store.project.sheets.first?.id }
        }
    }

    // MARK: - barra lateral de pedidos

    var ordersSidebar: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(store.project.week.isEmpty ? "sin semana" : store.project.week)
                .font(.headline)
                .padding(8)
            Divider()
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 8) {
                    ForEach(store.project.orders.filter { $0.mode != nil || !$0.edibleLinks.isEmpty }) { o in
                        OrderCard(order: o, store: store)
                    }
                }
                .padding(8)
            }
            Divider()
            Text(store.statusMessage)
                .font(.caption)
                .foregroundColor(.secondary)
                .padding(6)
        }
    }

    // MARK: - editor central

    var editorPane: some View {
        VStack(spacing: 0) {
            if !store.project.sheets.isEmpty {
                ScrollView(.horizontal) {
                    HStack(spacing: 6) {
                        ForEach(Array(store.project.sheets.enumerated()), id: \.element.id) { i, s in
                            Button("\(i + 1). \(s.title)") {
                                store.selectedSheetId = s.id
                                store.selectedPieceId = nil
                            }
                            .buttonStyle(.bordered)
                            .tint(store.selectedSheetId == s.id ? .accentColor : .secondary)
                        }
                    }
                    .padding(6)
                }
                Divider()
            }
            GeometryReader { geo in
                SheetCanvasView(store: store)
                    .frame(width: geo.size.width, height: geo.size.height)
            }
            Divider()
            HStack {
                Text("modo:")
                Picker("modo", selection: $store.encuadreMode) {
                    Text("mover").tag(false)
                    Text("encuadre (arrastrar/rueda)").tag(true)
                }
                .pickerStyle(.segmented)
                .frame(maxWidth: 320)
                Spacer()
                let ps = store.project.pieces.filter { $0.sheetId == store.selectedSheetId }
                Text("\(ps.count) pieza(s) en esta hoja · hoja \((store.project.sheets.firstIndex(where: { $0.id == store.selectedSheetId }) ?? 0) + 1)/\(store.project.sheets.count)")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding(6)
        }
    }

    // MARK: - inspector de pieza

    var inspector: some View {
        Group {
            if let sel = store.selectedPieceId, let idx = store.project.pieces.firstIndex(where: { $0.id == sel }) {
                let p = store.project.pieces[idx]
                Form {
                    Section("Pieza") {
                        TextEditor(text: Binding(
                            get: { p.label },
                            set: { store.updatePiece(sel) { $0.label = $0 } }
                        ))
                        .frame(height: 48)
                        TextField("día", text: Binding(
                            get: { p.day },
                            set: { store.updatePiece(sel) { $0.day = $0 } }
                        ))
                        Picker("tamaño pastel", selection: Binding(
                            get: { p.size },
                            set: { store.updatePiece(sel) { $0.size = $0 } }
                        )) {
                            ForEach(Config.sizeOrder, id: \.self) { Text($0).tag($0) }
                        }
                        Picker("modo", selection: Binding(
                            get: { p.kind },
                            set: { store.updatePiece(sel) { $0.kind = $0 } }
                        )) {
                            Text("COMPLETA (círculo)").tag("circle")
                            Text("RECORTADA (fotito)").tag("cutout")
                        }
                        HStack {
                            TextField("ancho px", value: Binding(
                                get: { p.w },
                                set: { store.updatePiece(sel) { piece in
                                    piece.w = $0
                                    if piece.kind == "circle" { piece.h = $0 }
                                } }
                            ), format: .number)
                            TextField("alto px", value: Binding(
                                get: { p.h },
                                set: { store.updatePiece(sel) { piece in
                                    piece.h = $0
                                    if piece.kind == "circle" { piece.w = $0 }
                                } }
                            ), format: .number)
                        }
                        HStack {
                            Toggle("GORRITO", isOn: Binding(get: { p.gorrito }, set: { store.updatePiece(sel) { $0.gorrito = $0 } }))
                            Toggle("B/N", isOn: Binding(get: { p.bn }, set: { store.updatePiece(sel) { $0.bn = $0 } }))
                            Toggle("solo cabeza", isOn: Binding(get: { p.headOnly }, set: { store.updatePiece(sel) { $0.headOnly = $0 } }))
                        }
                        HStack {
                            Button("rotar 90°") { store.updatePiece(sel) { $0.rotation = ($0.rotation + 90).truncatingRemainder(dividingBy: 360) } }
                            Button("quitar fondo (Vision)") {
                                Task { store.statusMessage = await store.removeBackground(sel, headOnly: p.headOnly) ?? "fondo quitado" }
                            }
                        }
                        Picker("hoja", selection: Binding(
                            get: { p.sheetId },
                            set: { store.updatePiece(sel) { $0.sheetId = $0 } }
                        )) {
                            ForEach(store.project.sheets) { Text($0.title).tag($0.id) }
                        }
                        Button("quitar pieza", role: .destructive) { store.deletePiece(sel) }
                        if let o = store.project.orders.first(where: { $0.id == p.orderId }) {
                            Text("pedido: \(o.labelId) · foto: \(p.photoStatus)")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                }
                .formStyle(.grouped)
            } else {
                Text("Selecciona una pieza en la hoja")
                    .foregroundColor(.secondary)
                    .padding()
            }
        }
    }

    // MARK: - diálogo de importación

    var importSheet: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Importar página de Craft").font(.headline)
            Text("Pega el markdown de `blocks get <pageId> --format markdown` (o exporta la semana como Markdown en Craft). Si pegas el documento raíz, se elige la semana en curso.")
                .font(.caption)
                .foregroundColor(.secondary)
            Button("Elegir archivo…") { showFilePicker = true }
            TextEditor(text: $importText)
                .font(.system(size: 11, design: .monospaced))
                .frame(height: 220)
                .border(Color.gray.opacity(0.4))
            if !availableWeeks.isEmpty {
                Picker("semana", selection: Binding(get: { weekChoice ?? availableWeeks.first! }, set: { weekChoice = $0 })) {
                    ForEach(availableWeeks, id: \.self) { Text($0).tag(Optional($0)) }
                }
            }
            if let err = importError { Text(err).foregroundColor(.red).font(.caption) }
            HStack {
                Spacer()
                Button("Cancelar") { showImport = false }
                Button("Importar", role: .cancel) {
                    let r = store.importCraft(text: importText, sourceName: importSource, week: weekChoice)
                    if let err = r.error {
                        importError = err
                        availableWeeks = r.weeks
                    } else {
                        statusReset("semana \(r.week): \(r.orders) pedidos")
                        showImport = false
                        importError = nil
                    }
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .padding()
        .frame(minWidth: 560)
    }

    func statusReset(_ s: String) { store.statusMessage = s }
}

struct OrderCard: View {
    let order: Order
    @ObservedObject var store: ProjectStore
    @State private var showUpload = false

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack {
                Text("\(order.num.map { $0 + ". " } ?? "")\(order.name) \(order.response.map { "#" + $0 } ?? "")")
                    .font(.subheadline).bold()
                Spacer()
                if order.gorrito { Tag("GORRITO", color: .green) }
                if order.bn { Tag("B/N", color: .gray) }
                if order.manual { Tag("manual", color: .orange) }
                if order.imageMissing { Tag("sin imagen", color: .yellow) }
            }
            Text("\(order.size.isEmpty ? "?" : order.size)\(order.shape == "otro" ? " · forma no redonda" : "") · \(order.mode ?? "?") · \(order.day)")
                .font(.caption).foregroundColor(.secondary)
            ForEach(order.edibleLinks, id: \.self) { u in
                Text(u.count > 60 ? String(u.prefix(57)) + "…" : u)
                    .font(.caption2).foregroundColor(.blue)
                    .lineLimit(1)
            }
            HStack {
                StatusPill(status: order.status, reason: order.statusReason)
                Spacer()
            }
            HStack(spacing: 4) {
                Button("bajar") { Task { await store.fetchOrder(order.id) } }
                Button("subir…") { showUpload = true }
                Button("crear pieza") { store.createPiece(order.id) }
                Button("hecha") { store.setOrderStatus(order.id, "hecha", "hecha en otro diseño") }
                Button("excluir") { store.setOrderStatus(order.id, "excluida", "excluida a mano") }
            }
            .font(.caption)
        }
        .padding(6)
        .background(Color(nsColor: .controlBackgroundColor))
        .cornerRadius(8)
        .fileImporter(isPresented: $showUpload, allowedContentTypes: [.image]) { res in
            if case .success(let url) = res, let data = try? Data(contentsOf: url) {
                store.upload(order.id, data: data, filename: url.lastPathComponent)
            }
        }
    }
}

struct Tag: View {
    let text: String
    let color: Color
    var body: some View {
        Text(text).font(.caption2).padding(.horizontal, 4).background(color.opacity(0.25)).cornerRadius(4)
    }
}

struct StatusPill: View {
    let status: String
    let reason: String
    var body: some View {
        Text(status + (reason.isEmpty ? "" : ": " + reason))
            .font(.caption2)
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(color.opacity(0.25))
            .cornerRadius(8)
    }
    var color: Color {
        switch status {
        case "lista": return .green
        case "hecha": return .blue
        case "excluida": return .red
        default: return .yellow
        }
    }
}
