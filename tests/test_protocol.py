"""Pruebas del protocolo snf-pulse-v1 y de la lectura de la configuración. Se corren con:
    python3 -m unittest discover -s tests -v
Requieren python3-cryptography. No tocan la red ni el nodo."""

import json
import os
import stat
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import pulse  # noqa: E402

with open(os.path.join(HERE, "vectors.json"), encoding="utf-8") as f:
    V = json.load(f)


class Protocolo(unittest.TestCase):
    def setUp(self):
        self.agent_id, self.secret = pulse.parse_token(V["token"])
        self.key = pulse.derive_key(self.agent_id, self.secret)

    def test_llave_igual_que_el_servidor(self):
        self.assertEqual(self.key.hex(), V["key_hex"])

    def test_abre_lo_que_cifra_el_servidor(self):
        vec = V["server_sealed_req"]
        self.assertEqual(pulse.open_envelope(self.key, vec["direction"], self.agent_id, vec["envelope"], check_time=False), vec["plain"])

    def test_su_propio_sobre_es_el_del_vector(self):
        vec = V["agent_sealed_res"]
        env = pulse.seal(self.key, "res", self.agent_id, vec["plain"], ts=vec["envelope"]["ts"], nonce=bytes([9] * 12))
        self.assertEqual(pulse.open_envelope(self.key, "res", self.agent_id, env, check_time=False), vec["plain"])

    def test_rechaza_sobres_alterados(self):
        vec = V["server_sealed_req"]
        env = dict(vec["envelope"])
        with self.assertRaises(Exception):
            pulse.open_envelope(self.key, "res", self.agent_id, env, check_time=False)  # otra dirección
        env["ts"] += 1
        with self.assertRaises(Exception):
            pulse.open_envelope(self.key, "req", self.agent_id, env, check_time=False)  # marca de tiempo alterada
        with self.assertRaises(Exception):
            pulse.open_envelope(self.key, "req", self.agent_id, vec["envelope"])  # fuera de la ventana de 5 min
        otra = pulse.derive_key(self.agent_id, "B" * 52)
        with self.assertRaises(Exception):
            pulse.open_envelope(otra, "req", self.agent_id, vec["envelope"], check_time=False)  # otro token

    def test_ida_y_vuelta_con_hora_actual(self):
        env = pulse.seal(self.key, "req", self.agent_id, {"schema": "subnetflow-node-1", "node": "pve"})
        self.assertLessEqual(abs(env["ts"] - int(time.time())), 2)
        self.assertEqual(pulse.open_envelope(self.key, "req", self.agent_id, env)["node"], "pve")

    def test_token_mal_formado(self):
        for bad in ("", "snfp_corto_x", V["token"].replace("snfp_", "snfx_"), V["token"] + "Z"):
            with self.assertRaises(ValueError):
                pulse.parse_token(bad)


class Configuracion(unittest.TestCase):
    def _conf(self, text, mode=0o600):
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.chmod(path, mode)
        self.addCleanup(os.remove, path)
        return path

    def test_lee_url_y_token(self):
        c = pulse.load_conf(self._conf("SNF_URL=https://snf.example.test/\nSNF_TOKEN=%s\n" % V["token"]))
        self.assertEqual(c["url"], "https://snf.example.test")
        self.assertEqual(c["key"].hex(), V["key_hex"])

    def test_token_vacio_o_incompleto_da_un_mensaje_claro(self):
        for token in ("", "snfp_corto"):
            with self.assertRaises(SystemExit) as cm:
                pulse.load_conf(self._conf("SNF_URL=https://snf.example.test\nSNF_TOKEN=%s\n" % token))
            self.assertIn("--set-token", str(cm.exception.code))

    def test_exige_permisos_600_y_https(self):
        with self.assertRaises(SystemExit):
            pulse.load_conf(self._conf("SNF_URL=https://snf.example.test\nSNF_TOKEN=%s\n" % V["token"], mode=0o644))
        with self.assertRaises(SystemExit):
            pulse.load_conf(self._conf("SNF_URL=http://snf.example.test\nSNF_TOKEN=%s\n" % V["token"]))


class Recoleccion(unittest.TestCase):
    def test_lee_la_configuracion_de_un_lxc(self):
        self.assertEqual(pulse._kv("name=eth0,bridge=vmbr0,ip=192.0.2.10/24,tag=40"),
                         {"name": "eth0", "bridge": "vmbr0", "ip": "192.0.2.10/24", "tag": "40"})

    def test_muestra_de_cpu_en_rango(self):
        if not os.path.exists("/proc/stat"):
            self.skipTest("sin /proc/stat")
        v = pulse.cpu_sample(0.2)
        self.assertTrue(v is None or 0 <= v <= 100)


if __name__ == "__main__":
    unittest.main()
