using System;
using System.Collections.Generic;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;

namespace ChatAI.AutoCAD2023 {
    internal static class CadTools {
        internal static Dictionary<string, object> Boundary(Document doc, string handle) {
            using (doc.LockDocument())
            using (var tr = doc.Database.TransactionManager.StartTransaction()) {
                var id = doc.Database.GetObjectId(false, new Handle(Convert.ToInt64(handle, 16)), 0);
                var poly = tr.GetObject(id, OpenMode.ForRead) as Polyline;
                var table = (BlockTable)tr.GetObject(doc.Database.BlockTableId, OpenMode.ForRead);
                if (poly == null || !poly.Closed || poly.OwnerId != table[BlockTableRecord.ModelSpace] ||
                    Math.Abs(poly.Elevation) > 1e-8 || (poly.Normal - Vector3d.ZAxis).Length > 1e-8 ||
                    poly.NumberOfVertices < 3 || poly.NumberOfVertices > 500)
                    throw new ArgumentException("Chọn polyline kín trong ModelSpace, phẳng XY cao độ 0, 3–500 đỉnh.");
                var vertices = new List<double[]>();
                for (int i = 0; i < poly.NumberOfVertices; i++) {
                    if (Math.Abs(poly.GetBulgeAt(i)) > 1e-12) throw new ArgumentException("Chưa hỗ trợ cạnh cung tròn; chọn polyline cạnh thẳng.");
                    var p = poly.GetPoint3dAt(i); vertices.Add(new[] { p.X, p.Y });
                }
                return new Dictionary<string, object> { { "handle", handle }, { "boundary", vertices }, { "units_header", doc.Database.Insunits.ToString() } };
            }
        }
        internal static string Inspect(Document doc) {
            using (doc.LockDocument())
            using (var tr = doc.Database.TransactionManager.StartTransaction()) {
                var rows = new List<object>();
                var selected = doc.Editor.SelectImplied();
                if (selected.Status == Autodesk.AutoCAD.EditorInput.PromptStatus.OK) {
                    foreach (var id in selected.Value.GetObjectIds()) {
                        if (rows.Count >= 100) break;
                        var entity = tr.GetObject(id, OpenMode.ForRead) as Entity;
                        if (entity == null) continue;
                        rows.Add(new { handle = entity.Handle.ToString(), type = entity.GetType().Name, layer = entity.Layer });
                    }
                }
                return ChatClient.Json.Serialize(new { drawing = System.IO.Path.GetFileName(doc.Name),
                    units = doc.Database.Insunits.ToString(), coordinates = "WCS", selected = rows });
            }
        }
        private static double Number(object value) {
            if (!(value is int || value is long || value is decimal || value is double || value is float))
                throw new ArgumentException("Tọa độ/kích thước phải là số.");
            var n = Convert.ToDouble(value);
            if (double.IsNaN(n) || double.IsInfinity(n) || Math.Abs(n) > 1e9) throw new ArgumentException("Số ngoài giới hạn.");
            return n;
        }
        private static Point3d Point(object value) {
            var a = value as System.Collections.IList;
            if (a == null || a.Count != 3) throw new ArgumentException("Điểm phải có [x,y,z].");
            return new Point3d(Number(a[0]), Number(a[1]), Number(a[2]));
        }
        internal static int Apply(Document doc, string json) {
            var plan = ChatClient.Json.Deserialize<Dictionary<string, object>>(json);
            if (plan.Count != 1 || !plan.ContainsKey("operations")) throw new ArgumentException("Cần JSON operations.");
            var ops = plan["operations"] as System.Collections.IList;
            if (ops == null || ops.Count == 0 || ops.Count > 100) throw new ArgumentException("Chỉ nhận 1–100 thao tác.");
            using (doc.LockDocument())
            using (var tr = doc.Database.TransactionManager.StartTransaction()) {
                var table = (BlockTable)tr.GetObject(doc.Database.BlockTableId, OpenMode.ForRead);
                var space = (BlockTableRecord)tr.GetObject(table[BlockTableRecord.ModelSpace], OpenMode.ForWrite);
                foreach (var raw in ops) {
                    var op = raw as Dictionary<string, object>;
                    if (op == null || !op.ContainsKey("type")) throw new ArgumentException("Thiếu type.");
                    Entity entity;
                    if (Equals(op["type"], "line") && op.Count == 3) {
                        var start = Point(op["start"]); var end = Point(op["end"]);
                        if (start.DistanceTo(end) < 1e-9) throw new ArgumentException("Đường thẳng có chiều dài bằng 0.");
                        entity = new Line(start, end);
                    } else if (Equals(op["type"], "circle") && op.Count == 3) {
                        var radius = Number(op["radius"]);
                        if (radius <= 0) throw new ArgumentException("Bán kính phải dương.");
                        entity = new Circle(Point(op["center"]), Vector3d.ZAxis, radius);
                    } else throw new ArgumentException("Chỉ hỗ trợ line/circle; không thực thi mã AI.");
                    space.AppendEntity(entity); tr.AddNewlyCreatedDBObject(entity, true);
                }
                // Any invalid operation aborts the entire transaction.
                tr.Commit();
            }
            doc.Editor.Regen(); return ops.Count;
        }
    }
}
