"""Embed web-demo files into work.js so the existing Worker can serve the site."""
from pathlib import Path
import base64
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    html = (ROOT / "web-demo" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "web-demo" / "styles.css").read_text(encoding="utf-8")
    js = (ROOT / "web-demo" / "app.js").read_text(encoding="utf-8")
    vendor = ROOT / "web-demo" / "vendor"
    for name in ("katex.min.js", "auto-render.min.js", "highlight.min.js"):
        code = (vendor / name).read_text(encoding="utf-8")
        html = html.replace('<script src="vendor/' + name + '"></script>', '<script>' + code.replace('</script', '<\\/script') + '</script>')
    katex_css = (vendor / "katex.min.css").read_text(encoding="utf-8")
    katex_css = re.sub(r'url\((fonts/[^)]+\.woff2)\)', lambda m: 'url(data:font/woff2;base64,' + base64.b64encode((vendor / m[1]).read_bytes()).decode() + ')', katex_css)
    html = html.replace('<link rel="stylesheet" href="vendor/katex.min.css">', '<style>' + katex_css + '</style>')
    version = hashlib.sha256(js.encode("utf-8")).hexdigest()[:12]
    css_version = hashlib.sha256(css.encode("utf-8")).hexdigest()[:12]
    html = re.sub(r'href="styles\.css(?:\?[^"<>]*)?"', f'href="/assets/styles-{css_version}.css"', html)
    html = re.sub(r'src="app\.js(?:\?[^"<>]*)?"', f'src="/assets/app-{version}.js"', html)
    png = base64.b64encode((ROOT / "web-demo" / "logo-web.png").read_bytes()).decode("ascii")
    fn = (
        "function serveWebApp(path){\n"
        " const files={\n"
        f"  '/':['text/html; charset=utf-8',{json.dumps(html)}],\n"
        f"  '/index.html':['text/html; charset=utf-8',{json.dumps(html)}],\n"
        f"  '/styles.css':['text/css; charset=utf-8',{json.dumps(css)}],\n"
        f"  '/app.js':['application/javascript; charset=utf-8',{json.dumps(js)}],\n"
        f"  '/logo.png':['image/png',{json.dumps(png)},true],\n"
        f"  '/favicon.ico':['image/png',{json.dumps(png)},true]\n"
        " };\n"
        f" files['/assets/app-{version}.js']=files['/app.js'];\n"
        f" files['/assets/styles-{css_version}.css']=files['/styles.css'];\n"
        " const file=files[path];\n"
        " if(!file)return null;\n"
        " const body=file[2]?Uint8Array.from(atob(file[1]),c=>c.charCodeAt(0)):file[1];\n"
        " return new Response(body,{headers:{'Content-Type':file[0],'Cache-Control':path==='/'||path==='/index.html'?'no-store':'public, max-age=600','X-Content-Type-Options':'nosniff'}});\n"
        "}\n"
    )
    work_path = ROOT / "work.js"
    work = work_path.read_text(encoding="utf-8")
    start, end = "// <web-app>", "// </web-app>"
    block = f"{start}\n{fn}{end}\n"
    if start in work:
        work = re.sub(
            re.escape(start) + r".*?" + re.escape(end) + r"\n",
            lambda _: block,
            work,
            count=1,
            flags=re.S,
        )
    else:
        work = work.replace("export default {", block + "export default {", 1)
    needle = "if(path==='/api/health'&&request.method==='GET')return respond(reply({success:true,app:'Chat AI',version:VERSION,database_configured:Boolean(env.DB),cloud_optional:true}));"
    insert = needle + "\n  if(request.method==='GET'){const page=serveWebApp(path);if(page)return respond(page);}"
    exported = work.split("export default", 1)[1]
    if "serveWebApp(path)" not in exported:
        if needle not in work:
            raise SystemExit("health handler not found")
        work = work.replace(needle, insert, 1)
    work_path.write_text(work, encoding="utf-8")
    print("embedded web app into work.js", work_path.stat().st_size)


if __name__ == "__main__":
    main()
