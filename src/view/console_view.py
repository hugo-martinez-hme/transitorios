# src/view/console_view.py
from typing import Dict, Optional
from src.model.dtos import DiagnosisResult, VALID_STATES


class ConsoleView:
    """Vista CLI concordante con Figura 1 y Sección 7 del documento de arquitectura."""

    def mostrar_menu(self) -> str:
        print("\n" + "=" * 74)
        print(" === SISTEMA BAYESIANO DE DIAGNÓSTICO DE TRANSITORIOS ASTROFÍSICOS (RAIN) ===")
        print("=" * 74)
        print("Modo de entrada: [1] Estados discretos  [2] Mediciones físicas continuas  [3] Lote JSON  [0] Salir")
        return input("-> Selección: ").strip()

    def _preguntar_estado(self, num: int, etiqueta: str, variable: str) -> Optional[str]:
        estados = VALID_STATES[variable]
        opciones_str = "  ".join([f"[{i+1}] {est}" for i, est in enumerate(estados)])
        print(f"  {num}. {etiqueta:<22}: {opciones_str}  [0] N/D")
        while True:
            sel = input("     -> Selección: ").strip()
            if sel in ("", "0"):
                return None
            if sel.isdigit() and 1 <= int(sel) <= len(estados):
                return estados[int(sel) - 1]
            print("     [!] Opción no válida. Introduzca un número de la lista o 0 para desconocido.")

    def solicitar_discretas(self) -> Dict[str, Optional[str]]:
        print("\nIntroduzca las evidencias observadas (Pulse [0] si el dato aún es desconocido / no medido):")
        return {
            "galaxia": self._preguntar_estado(1, "Galaxia Anfitriona", "Galaxia_Anfitriona"),
            "ubicacion": self._preguntar_estado(2, "Ubicación Galáctica", "Ubicacion_Galactica"),
            "color": self._preguntar_estado(3, "Color Observado", "Color_Observado"),
            "magnitud": self._preguntar_estado(4, "Magnitud Aparente", "Magnitud_Aparente"),
            "anchura_lineas": self._preguntar_estado(5, "Líneas Espectrales", "Anchura_Lineas"),
            "rayos_x": self._preguntar_estado(6, "Emisión Rayos X", "Emision_RayosX"),
            "curva_luz": self._preguntar_estado(7, "Forma Curva de Luz", "Forma_Curva_Luz"),
        }

    @staticmethod
    def _leer_float_opcional(prompt: str) -> Optional[float]:
        val = input(prompt).strip()
        return float(val) if val else None

    def solicitar_continuas(self) -> Dict[str, float | str | None]:
        print("\nIntroduzca las mediciones físicas continuas (Pulse Enter para omitir un dato no medido):")
        galaxia = self._preguntar_estado(1, "Galaxia Anfitriona", "Galaxia_Anfitriona")
        r_kpc = self._leer_float_opcional("  2. Distancia galactocéntrica r (kpc) [<1 Nuclear, 1-15 Brazo, >15 Halo]: ")
        g_minus_r = self._leer_float_opcional("  3. Índice de color (g - r) (mag) [<0 Azul, 0-0.5 Neutro, >0.5 Rojo]: ")
        m_v = self._leer_float_opcional("  4. Magnitud aparente óptica m_V (mag) [<17 Brillante, 17-19.5 Interm., >19.5 Débil]: ")
        fwhm_kms = self._leer_float_opcional("  5. Ensanchamiento Doppler FWHM (km/s) [>3000 Anchas, <3000 Estrechas, 0 Ausentes]: ")
        l_x = self._leer_float_opcional("  6. Luminosidad Rayos X L_X (erg/s) [>1e42 Intensa, 1e39-1e42 Débil, 0 Nula]: ")
        curva_luz = self._preguntar_estado(7, "Forma Curva de Luz", "Forma_Curva_Luz")

        return {
            "galaxia": galaxia,
            "r_kpc": r_kpc,
            "g_minus_r": g_minus_r,
            "m_v": m_v,
            "fwhm_kms": fwhm_kms,
            "l_x": l_x,
            "curva_luz": curva_luz,
        }

    def mostrar_diagnostico(
        self, resultado: DiagnosisResult, evidencias: Dict[str, str] | None = None, titulo: str = ""
    ) -> None:
        print("\n" + "-" * 74)
        if titulo:
            print(f" {titulo}")
            print("-" * 74)
        if evidencias is not None:
            print(f" Evidencias observadas (e): {evidencias if evidencias else 'Ninguna (Prior)'}")
            print("-" * 74)

        print(" 1. DISTRIBUCIÓN POSTERIOR DE DIAGNÓSTICO P(Tipo_Transitorio | e)")
        ordenados = sorted(resultado.prob_transitorio.items(), key=lambda x: x[1], reverse=True)
        for tipo, prob in ordenados:
            bloques = int(round(prob * 25))
            barra = "█" * bloques + "░" * (25 - bloques)
            print(f"  * {tipo:<18} : {barra}  {prob * 100:5.1f} %")

        print(f"\n  [DIAGNÓSTICO]: {resultado.clase_predicha} ({resultado.confianza * 100:.1f}%) "
              f"| Entropía H = {resultado.entropia_shannon:.2f} bits")

        print("\n 2. INFERENCIA EXPLICATIVA DE FÍSICA LATENTE (NIVEL 3)")
        print(f"  * {resultado.resumen_fisica_latente()}")

        print(f"\n 3. RECOMENDADOR DE SEGUIMIENTO TELESCÓPICO (ENTROPÍA H = {resultado.entropia_shannon:.2f} bits)")
        if not resultado.ganancia_info_ig:
            print("  [OK] Todos los observables han sido medidos.")
        elif resultado.entropia_shannon < 0.25:
            print("  [OK] Diagnóstico concluyente (H < 0.25 bits); no requiere más observaciones.")
        else:
            for idx, (obs, ig) in enumerate(list(resultado.ganancia_info_ig.items())[:2], start=1):
                reduccion = (ig / resultado.entropia_shannon * 100) if resultado.entropia_shannon > 0 else 0.0
                tag = "[RECOMENDADO]" if idx == 1 else "[SECUNDARIO] "
                print(f"  {idx}º {tag} {obs:<20} -> Ganancia esperada IG = {ig:.3f} bits (-{reduccion:.0f}% incertidumbre)")
        print("=" * 74)
