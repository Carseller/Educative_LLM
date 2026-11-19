"""Gerçek LLMIstemci'yi, vLLM'i taklit eden küçük bir HTTP sunucusuna karşı sınar (GPU gerekmez)."""
import asyncio
import copy
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from src.llm_istemci import LLMIstemci

pytest.importorskip("openai")


class _Isleyici(BaseHTTPRequestHandler):
    istekler: list = []
    bes_yuz_kalan = 0

    def log_message(self, *a):
        pass

    def _yanit(self, kod: int, govde: dict) -> None:
        veri = json.dumps(govde).encode()
        self.send_response(kod)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(veri)))
        self.end_headers()
        self.wfile.write(veri)

    def do_POST(self):
        govde = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Isleyici.istekler.append(govde)
        if _Isleyici.bes_yuz_kalan > 0:
            _Isleyici.bes_yuz_kalan -= 1
            return self._yanit(500, {"error": {"message": "geçici"}})
        if "response_format" in govde:      # bu sürüm response_format desteklemiyor gibi davran
            return self._yanit(400, {"error": {"message": "response_format desteklenmiyor"}})
        dusunme = govde.get("chat_template_kwargs", {}).get("enable_thinking")
        if "structured_outputs" in govde or "guided_json" in govde:
            mesaj = {"role": "assistant", "content": json.dumps({"mesaj": "24 buldum", "verilen_deger": 24})}
        elif dusunme:
            mesaj = {"role": "assistant", "content": "Yarısını nasıl bulursun?", "reasoning_content": "Answer is 72."}
        else:
            mesaj = {"role": "assistant", "content": "düz"}
        self._yanit(200, {"id": "x", "object": "chat.completion", "created": 0, "model": govde["model"],
                          "choices": [{"index": 0, "message": mesaj, "finish_reason": "stop"}],
                          "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})


@pytest.fixture
def sunucu():
    s = ThreadingHTTPServer(("127.0.0.1", 0), _Isleyici)
    t = threading.Thread(target=s.serve_forever, daemon=True)
    t.start()
    _Isleyici.istekler = []
    _Isleyici.bes_yuz_kalan = 0
    yield f"http://127.0.0.1:{s.server_address[1]}/v1"
    s.shutdown()


def _cfg(cfg, url):
    c = copy.deepcopy(cfg)
    c.update(api_url=url, json_zorlama="auto", ag_yeniden_deneme=2)
    c["ogretmen_ornekleme"] = {"temperature": 0.6, "top_p": 0.95, "max_tokens": 100, "top_k": 20}
    return c


def test_ogretmen_iz_ayri_ve_parametreler(cfg, sunucu):
    ist = LLMIstemci(_cfg(cfg, sunucu))
    y = asyncio.run(ist.ogretmen("sistem", [{"role": "user", "content": "soru"}], seed=7))
    assert y.iz == "Answer is 72." and y.icerik == "Yarısını nasıl bulursun?"
    istek = _Isleyici.istekler[-1]
    assert istek["chat_template_kwargs"] == {"enable_thinking": True}
    assert istek["top_k"] == 20 and istek["seed"] == 7 and istek["messages"][0]["role"] == "system"


def test_json_auto_geri_duser_ve_hatirlar(cfg, sunucu):
    ist = LLMIstemci(_cfg(cfg, sunucu))
    y = asyncio.run(ist.ogrenci_json(None, [{"role": "user", "content": "x"}], {"type": "object"}))
    assert y.js == {"mesaj": "24 buldum", "verilen_deger": 24}
    assert ist.json_modu == "structured_outputs"
    assert _Isleyici.istekler[-1]["chat_template_kwargs"] == {"enable_thinking": False}


def test_ag_hatasi_yeniden_denenir_ve_sayilir(cfg, sunucu):
    _Isleyici.bes_yuz_kalan = 1
    ist = LLMIstemci(_cfg(cfg, sunucu))
    y = asyncio.run(ist.ogretmen("s", [{"role": "user", "content": "x"}]))
    assert y.icerik and y.ag_hatasi == 1 and ist.istatistik["ag_hatasi"] == 1
