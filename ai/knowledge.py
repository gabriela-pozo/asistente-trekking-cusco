"""Base de conocimiento: fragmentos de data/knowledge y búsqueda con TF-IDF.

Cada archivo .md tiene una cabecera '---' con tema, fecha, fuentes y estado, y
secciones que empiezan con '## '. Cada sección es un fragmento: lo mínimo que se
le pasa al modelo para que responda con información verificada.

La base está en español, así que la búsqueda también se hace en español: la
consulta se arma desde el perfil del turista (que ya viene normalizado en
español), no desde el mensaje original, que puede estar en cualquier idioma.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Palabras muy comunes del español que no ayudan a distinguir un fragmento de otro.
PALABRAS_VACIAS = (
    "a al algo con como de del el en es esta este hay la las lo los mas o para pero por que se si sin "
    "su sus un una uno y ya"
).split()

# Archivo de la base que corresponde a cada trek del perfil.
# Código del trek en el perfil -> archivo de data/knowledge y palabras para la búsqueda en español
TREKS = {
    "salkantay": ("salkantay", "salkantay trek"),
    "camino_inca": ("camino_inca", "camino inca permisos"),
    "camino_inca_corto": ("camino_inca_corto", "camino inca corto"),
    "lares": ("lares", "lares trek"),
    "choquequirao": ("choquequirao", "choquequirao trek"),
    "inca_jungle": ("inca_jungle", "inca jungle"),
}
ARCHIVO_POR_TREK = {codigo: archivo for codigo, (archivo, _) in TREKS.items()}
ARCHIVO_RESERVA = "condiciones_reserva"
MESES_DE_LLUVIA = {10, 11, 12, 1, 2, 3, 4}
FEBRERO = 2


@dataclass
class Fragmento:
    archivo: str
    titulo: str
    texto: str
    actualizado: str = ""
    fuentes: list[str] = field(default_factory=list)
    estado: str = ""

    def para_prompt(self) -> str:
        """Cómo se le muestra el fragmento al modelo: con su origen y su fecha."""
        return f"[{self.archivo} · {self.titulo} · actualizado {self.actualizado}]\n{self.texto}"


def leer_cabecera(contenido: str) -> tuple[dict, str]:
    """Separa la cabecera '---' del cuerpo. Devuelve (metadatos, cuerpo)."""
    meta: dict = {"fuentes": []}
    if not contenido.startswith("---"):
        return meta, contenido
    _, cabecera, cuerpo = contenido.split("---", 2)
    clave_actual = None
    for linea in cabecera.strip().splitlines():
        limpia = linea.strip()
        if limpia.startswith("- ") and clave_actual == "fuentes":
            meta["fuentes"].append(limpia[2:].strip())
        elif ":" in limpia:
            clave, valor = limpia.split(":", 1)
            clave_actual = clave.strip()
            if valor.strip():
                meta[clave_actual] = valor.strip()
    return meta, cuerpo


def cargar_fragmentos(carpeta: str | Path) -> list[Fragmento]:
    """Un fragmento por cada sección '## ' de cada archivo .md."""
    fragmentos: list[Fragmento] = []
    for ruta in sorted(Path(carpeta).glob("*.md")):
        meta, cuerpo = leer_cabecera(ruta.read_text(encoding="utf-8"))
        for parte in re.split(r"^## ", cuerpo, flags=re.MULTILINE)[1:]:
            titulo, _, texto = parte.partition("\n")
            fragmentos.append(Fragmento(
                archivo=ruta.stem,
                titulo=titulo.strip(),
                texto=texto.strip(),
                actualizado=meta.get("actualizado", ""),
                fuentes=meta.get("fuentes", []),
                estado=meta.get("estado", ""),
            ))
    return fragmentos


class BaseConocimiento:
    def __init__(self, carpeta: str | Path):
        self.fragmentos = cargar_fragmentos(carpeta)
        if not self.fragmentos:
            raise ValueError(f"No hay fragmentos en {carpeta}")
        self._vectorizador = TfidfVectorizer(
            strip_accents="unicode",   # "días" y "dias" cuentan como la misma palabra
            lowercase=True,
            ngram_range=(1, 2),        # también pares de palabras: "camino inca", "bolsa dormir"
            stop_words=PALABRAS_VACIAS,
        )
        # El nombre del archivo y el título también cuentan para la búsqueda.
        documentos = [f"{f.archivo.replace('_', ' ')} {f.titulo} {f.texto}" for f in self.fragmentos]
        self._matriz = self._vectorizador.fit_transform(documentos)

    def puntajes(self, consulta: str) -> list[float]:
        """Parecido (0 a 1) entre la consulta y cada fragmento."""
        vector = self._vectorizador.transform([consulta])
        return cosine_similarity(vector, self._matriz).ravel().tolist()

    def buscar(self, consulta: str, k: int = 6, archivos_prioritarios: list[str] | None = None,
               por_archivo: int = 2) -> list[Fragmento]:
        """Devuelve los fragmentos más parecidos a la consulta.

        De cada archivo prioritario entran siempre sus `por_archivo` mejores
        fragmentos, aunque la consulta no se parezca a ellos. Después se completa
        hasta `k` con los más parecidos del resto. Si los prioritarios ya suman
        más de `k`, se devuelven todos ellos: la garantía pesa más que el límite.
        """
        puntajes = self.puntajes(consulta)
        # Del más parecido al menos parecido; a igual puntaje, el orden del archivo.
        orden = sorted(range(len(self.fragmentos)), key=lambda i: (-puntajes[i], i))

        elegidos: list[int] = []
        for archivo in dict.fromkeys(archivos_prioritarios or []):  # sin repetidos, en orden
            del_archivo = [i for i in orden if self.fragmentos[i].archivo == archivo]
            elegidos += [i for i in del_archivo[:por_archivo] if i not in elegidos]

        for i in orden:
            if len(elegidos) >= k:
                break
            if puntajes[i] > 0 and i not in elegidos:
                elegidos.append(i)
        return [self.fragmentos[i] for i in elegidos]


def consulta_desde_perfil(perfil) -> str:
    """Arma la búsqueda en español a partir del perfil del turista.

    El perfil ya viene en español aunque el turista haya escrito en otro idioma:
    los treks son códigos fijos y los temas se extraen en español.
    """
    treks = getattr(perfil, "treks_de_interes", None) or []
    temas = getattr(perfil, "temas_consulta", None) or []
    mes = getattr(perfil, "mes_viaje", None)

    partes = [TREKS[t][1] if t in TREKS else "trek alternativa" for t in treks]
    partes += temas
    if mes in MESES_DE_LLUVIA:
        partes.append("temporada de lluvias")
    if mes == FEBRERO and "camino_inca" in treks:
        partes.append("cierre anual febrero alternativa salkantay")
    partes.append("depósito para reservar")
    return " ".join(partes)


def archivos_desde_perfil(perfil) -> list[str]:
    """Archivos que siempre deben consultarse: los del trek pedido y las condiciones de reserva.

    Si pide el Camino Inca en febrero (cerrado), se agrega el Salkantay, que es la
    alternativa que ofrece la cotización.
    """
    treks = getattr(perfil, "treks_de_interes", None) or []
    archivos = [ARCHIVO_POR_TREK[t] for t in treks if t in ARCHIVO_POR_TREK]
    if getattr(perfil, "mes_viaje", None) == FEBRERO and "camino_inca" in treks:
        archivos.append("salkantay")
    archivos.append(ARCHIVO_RESERVA)
    return list(dict.fromkeys(archivos))
