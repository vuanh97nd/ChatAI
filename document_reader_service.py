"""Optional DOCUMENT_READER service. Run behind an authenticated private service binding."""
from fastapi import FastAPI, Request, HTTPException
from assistant.document_reader import read_bytes, MAX_BYTES
app=FastAPI()
@app.post('/read')
async def read(request: Request):
    body=bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body)>MAX_BYTES: raise HTTPException(413,'Document exceeds 32 MiB')
    try: return read_bytes(bytes(body),request.query_params.get('name','document'),request.headers.get('content-type',''))
    except Exception as error: raise HTTPException(422,str(error)) from None
