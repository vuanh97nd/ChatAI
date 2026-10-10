"""Interrupt waiting for model IO; discard late results and never detach tools."""
from queue import Queue, Empty, Full
from threading import Event, Thread
import time


class CancellableClient:
    def __init__(self, client, cancel, cancelled, on_status=None):
        self.client,self.cancel,self.cancelled,self.on_status=client,cancel,cancelled,on_status

    def __getattr__(self,name):
        method=getattr(self.client,name)
        if name not in {'chat','generate','embed','embeddings','list','show','ps'}:return method
        def call(*args,**kwargs):
            values=self._receive(lambda:method(*args,**kwargs),bool(kwargs.get('stream')))
            if kwargs.get('stream'):return values
            try:return next(values)
            finally:values.close()
        return call

    def _receive(self,request,stream):
        if self.cancel.is_set():raise self.cancelled()
        queue=Queue(maxsize=4);abandoned=Event()
        def offer(value):
            while not abandoned.is_set():
                try:queue.put(value,timeout=.1);return
                except Full:pass
        def receive():
            response=None
            try:
                response=request()
                if stream:
                    for item in response:
                        if abandoned.is_set():break
                        offer(('value',item))
                else:offer(('value',response))
            except BaseException as error:offer(('error',error))
            finally:
                if stream and response is not None:
                    try:
                        close=getattr(response,'close',None)
                        if close:close()
                    except Exception:pass
                offer(('done',None))
        Thread(target=receive,daemon=True,name='ChatAI-local-model').start()
        started=last=time.monotonic()
        try:
            while True:
                if self.cancel.is_set():raise self.cancelled()
                try:kind,value=queue.get(timeout=.1)
                except Empty:
                    elapsed=time.monotonic()
                    if self.on_status and elapsed-last>=5:
                        self.on_status('Đang chờ AI trên máy · '+str(int(elapsed-started))+' giây')
                        last=elapsed
                    continue
                if self.cancel.is_set():raise self.cancelled()
                if kind=='done':return
                if kind=='error':raise value
                yield value
        finally:
            abandoned.set()
            if self.cancel.is_set():
                def close():
                    try:
                        fn=getattr(self.client,'close',None)
                        if fn:fn()
                    except Exception:pass
                Thread(target=close,daemon=True,name='ChatAI-close-model').start()
