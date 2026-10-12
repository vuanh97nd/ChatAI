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
                question, ask, answer, apply, status }) { item.Width = 350; layout.Controls.Add(item); }
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
                    target = Acad.DocumentManager.MdiActiveDocument;
                    if (target == null) throw new InvalidOperationException("Mở bản vẽ trước.");
                    var data = context.Checked ? CadTools.Inspect(target) : "Không gửi dữ liệu bản vẽ. Đơn vị/tọa độ do người dùng cung cấp.";
                    status.Text = "Đang chờ AI…";
                    answer.Text = await client.Ask(question.Text, data, provider.Text);
                    apply.Enabled = answer.Text.TrimStart().StartsWith("{"); status.Text = "Đã trả lời; chưa sửa bản vẽ.";
                } catch (System.Exception ex) { status.Text = ex.Message; }
                finally { SetBusy(false); }
            };
            apply.Click += delegate {
                if (busy) return;
                try {
                    if (target == null || target != Acad.DocumentManager.MdiActiveDocument)
                        throw new InvalidOperationException("Bản vẽ đã đổi; gửi yêu cầu mới.");
                    if (MessageBox.Show("Vẽ vào ModelSpace, tọa độ WCS, theo JSON đang hiển thị?", "Chat AI",
                        MessageBoxButtons.OKCancel) != DialogResult.OK) return;
                    status.Text = "Đã tạo " + CadTools.Apply(target, answer.Text) + " đối tượng. Không tự lưu.";
                    apply.Enabled = false;
                } catch (System.Exception ex) { status.Text = ex.Message; }
            };
        }
        private void SetBusy(bool value) { busy = value; login.Enabled = ask.Enabled = !value; }
        protected override void Dispose(bool disposing) { if (disposing) client.Dispose(); base.Dispose(disposing); }
    }
}
