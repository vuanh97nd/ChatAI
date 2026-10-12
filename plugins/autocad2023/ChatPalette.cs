using System;
using System.Drawing;
using System.Windows.Forms;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.Runtime;
using Autodesk.AutoCAD.Windows;
using Acad = Autodesk.AutoCAD.ApplicationServices.Application;

namespace ChatAI.AutoCAD2023 {
    public sealed class Plugin : IExtensionApplication {
        private static PaletteSet palette;
        private static ChatPanel panel;
        public void Initialize() { }
        [CommandMethod("CHATAIREGION")]
        public void SelectRegion() {
            if (panel == null) { Open(); }
            var doc = Acad.DocumentManager.MdiActiveDocument;
            if (doc == null) return;
            try {
                var options = new Autodesk.AutoCAD.EditorInput.PromptEntityOptions("\nChọn polyline kín vùng CDM: ");
                options.SetRejectMessage("\nCần polyline 2D.");
                options.AddAllowedClass(typeof(Autodesk.AutoCAD.DatabaseServices.Polyline), true);
                var selection = doc.Editor.GetEntity(options);
                if (selection.Status != Autodesk.AutoCAD.EditorInput.PromptStatus.OK) return;
                panel.SetBoundary(doc, selection.ObjectId.Handle.ToString());
            } catch (System.Exception ex) { doc.Editor.WriteMessage("\n" + ex.Message); }
        }
        public void Terminate() { if (panel != null) panel.Dispose(); }
        [CommandMethod("CHATAI", CommandFlags.Session)]
        public void Open() {
            if (palette == null) {
                panel = new ChatPanel();
                palette = new PaletteSet("Chat AI", new Guid("A94C1CCA-52F2-4F43-A07B-664791704A22"));
                palette.MinimumSize = new Size(320, 450); palette.Size = new Size(420, 650);
                palette.Add("Chat", panel);
            }
            palette.Visible = true;
        }
    }
    internal sealed class ChatPanel : UserControl {
        private readonly ChatClient client = new ChatClient();
        private readonly TextBox endpoint = new TextBox { Text = "https://chatai-backup.vuanh97nd1.workers.dev" };
        private readonly TextBox username = new TextBox();
        private readonly TextBox password = new TextBox { UseSystemPasswordChar = true };
        private readonly TextBox repository = new TextBox();
        private readonly Button browse = new Button { Text = "Chọn thư mục mã nguồn ChatAI", AutoSize = true };
        private readonly Button selectRegion = new Button { Text = "Chọn polyline vùng CDM", AutoSize = true };
        private Document boundaryDocument;
        private string boundaryHandle, boundarySnapshot;
        private readonly ComboBox provider = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList };
        private readonly TextBox question = new TextBox { Multiline = true, Height = 80 };
        private readonly TextBox answer = new TextBox { Multiline = true, ScrollBars = ScrollBars.Vertical, Height = 220 };
        private readonly Label status = new Label { AutoSize = true, Text = "Chưa đăng nhập" };
        private readonly CheckBox context = new CheckBox { Text = "Gửi thông tin đối tượng đang chọn", AutoSize = true };
        private readonly Button login = new Button { Text = "Đăng nhập", AutoSize = true };
        private readonly Button ask = new Button { Text = "Gửi", AutoSize = true };
        private readonly Button apply = new Button { Text = "Duyệt và vẽ JSON", AutoSize = true, Enabled = false };
        private Document target;
        private bool busy;
        internal ChatPanel() {
            var layout = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.TopDown,
                WrapContents = false, AutoScroll = true, Padding = new Padding(8) };
            Controls.Add(layout);
            provider.Items.AddRange(new object[] { "nvidia", "deepseek_flash" }); provider.SelectedIndex = 0;
            foreach (var item in new Control[] { new Label { Text = "Server HTTPS", AutoSize = true }, endpoint,
                new Label { Text = "Tài khoản", AutoSize = true }, username,
                new Label { Text = "Mật khẩu", AutoSize = true }, password, login, provider, context,
                repository, browse, selectRegion, question, ask, answer, apply, status }) { item.Width = 350; layout.Controls.Add(item); }
            selectRegion.Click += delegate {
                if (!busy && Acad.DocumentManager.MdiActiveDocument != null)
                    Acad.DocumentManager.MdiActiveDocument.SendStringToExecute("CHATAIREGION ", true, false, false);
            };
            browse.Click += delegate {
                using (var dialog = new FolderBrowserDialog()) {
                    dialog.Description = "Thư mục chứa assistant và .venv của ChatAI";
                    if (dialog.ShowDialog() == DialogResult.OK) repository.Text = dialog.SelectedPath;
                }
            };
            login.Click += async delegate {
                if (busy) return; SetBusy(true); apply.Enabled = false;
                try { await client.Login(endpoint.Text, username.Text, password.Text); password.Clear(); status.Text = "Đã đăng nhập"; }
                catch (System.Exception ex) { status.Text = ex.Message; }
                finally { SetBusy(false); }
            };
            ask.Click += async delegate {
                if (busy || string.IsNullOrWhiteSpace(question.Text)) return;
                SetBusy(true); apply.Enabled = false;
                try {
                    var current = Acad.DocumentManager.MdiActiveDocument;
                    if (target != current) client.ClearHistory();
                    target = current;
                    if (target == null) throw new InvalidOperationException("Mở bản vẽ trước.");
                    var data = context.Checked ? CadTools.Inspect(target) : "Không gửi dữ liệu bản vẽ. Đơn vị/tọa độ do người dùng cung cấp.";
                    if (boundaryDocument == target && boundaryHandle != null) {
                        var region = CadTools.Boundary(target, boundaryHandle);
                        if (ChatClient.Json.Serialize(region) != boundarySnapshot) throw new InvalidOperationException("Vùng đã thay đổi; chọn lại polyline.");
                        // Keep coordinates local: AI gets only identity/count, never redraws the boundary.
                        data += "\nVùng CDM đã chọn: handle=" + boundaryHandle + ", units_header=" + region["units_header"] +
                            ". Dùng cdm_boundary; vùng sẽ được plugin truyền trực tiếp. Người dùng cần xác nhận đơn vị hình học.";
                    }
                    status.Text = "Đang chờ AI…";
                    answer.Text = await client.Ask(question.Text, data, provider.Text);
                    apply.Enabled = answer.Text.TrimStart().StartsWith("{"); status.Text = "Đã trả lời; chưa sửa bản vẽ.";
                } catch (System.Exception ex) { status.Text = ex.Message; }
                finally { SetBusy(false); }
            };
            apply.Click += async delegate {
                if (busy) return;
                var consumed = false;
                try {
                    if (target == null || target != Acad.DocumentManager.MdiActiveDocument)
                        throw new InvalidOperationException("Bản vẽ đã đổi; gửi yêu cầu mới.");
                    var plan = ChatClient.Json.Deserialize<System.Collections.Generic.Dictionary<string, object>>(answer.Text);
                    if (plan.ContainsKey("action")) {
                        if (Equals(plan["action"], "cdm_boundary")) {
                            if (boundaryDocument != target || boundaryHandle == null) throw new InvalidOperationException("Chọn polyline vùng CDM trước.");
                            var region = CadTools.Boundary(target, boundaryHandle);
                            if (ChatClient.Json.Serialize(region) != boundarySnapshot) throw new InvalidOperationException("Vùng đã thay đổi; chọn lại và gửi yêu cầu mới.");
                            var parameters = plan["parameters"] as System.Collections.Generic.Dictionary<string, object>;
                            if (parameters == null) throw new ArgumentException("Thiếu parameters.");
                            parameters["boundary"] = region["boundary"];
                            plan["parameters"] = parameters;
                        }
                        var json = ChatClient.Json.Serialize(plan);
                        using (var dialog = new System.Windows.Forms.SaveFileDialog { Filter = "DXF (*.dxf)|*.dxf", FileName = "CDM-" + DateTime.Now.ToString("yyyyMMdd-HHmmss") + ".dxf", OverwritePrompt = true }) {
                            if (dialog.ShowDialog() != DialogResult.OK) return;
                            if (System.IO.File.Exists(dialog.FileName)) throw new InvalidOperationException("Chọn tên file mới; không ghi đè bản vẽ.");
                            if (MessageBox.Show("Tạo DXF mới theo JSON đang hiển thị và mở bản vẽ kết quả?", "CDM", MessageBoxButtons.OKCancel) != DialogResult.OK) return;
                            SetBusy(true); apply.Enabled = false; status.Text = "Đang tạo DXF CDM…";
                            var result = await CdmBridge.Render(repository.Text, json, dialog.FileName);
                            consumed = true;
                            status.Text = "Đã lưu: " + dialog.FileName + " · " + Convert.ToString(result["note"]);
                            try { Acad.DocumentManager.Open(dialog.FileName, false); }
                            catch (System.Exception) { status.Text = "DXF đã lưu tại " + dialog.FileName + "; mở bằng OPEN. Không tạo lại."; }
                        }
                        return;
                    }
                    if (MessageBox.Show("Vẽ vào ModelSpace, tọa độ WCS, theo JSON đang hiển thị?", "Chat AI",
                        MessageBoxButtons.OKCancel) != DialogResult.OK) return;
                    status.Text = "Đã tạo " + CadTools.Apply(target, answer.Text) + " đối tượng. Không tự lưu.";
                    consumed = true;
                } catch (System.Exception ex) { status.Text = ex.Message; }
                finally { SetBusy(false); if (consumed) apply.Enabled = false; }
            };
        }
        internal void SetBoundary(Document doc, string handle) {
            if (busy) throw new InvalidOperationException("Chờ yêu cầu hiện tại hoàn tất.");
            var region = CadTools.Boundary(doc, handle);
            boundaryDocument = doc; boundaryHandle = handle; boundarySnapshot = ChatClient.Json.Serialize(region);
            client.ClearHistory(); apply.Enabled = false;
            status.Text = "Đã chọn vùng " + handle + ". Nhập D, sx, sy (m), đơn vị vùng, khoảng lùi mép và góc lưới.";
        }
        private void SetBusy(bool value) {
            busy = value; login.Enabled = ask.Enabled = browse.Enabled = selectRegion.Enabled = !value;
            question.ReadOnly = answer.ReadOnly = repository.ReadOnly = value;
        }
        protected override void Dispose(bool disposing) { if (disposing) client.Dispose(); base.Dispose(disposing); }
    }
}
