# src/view/console_view.py
from typing import Dict, Optional
from src.model.dtos import DiagnosisResult, VALID_STATES


class ConsoleView:
    def mostrar_menu(self) -> str:
        print("\n" + "=" * 74)
        print(" === SISTEMA BAYESIANO DE DIAGNÓSTICO DE TRANSITORIOS ASTROFÍSICOS (RAIN) ===")
        print("=" * 74)
        print("Modo de entrada:")
        print("  [1] Estados discretos (Selección guiada)")
        print("  [2] Mediciones físicas continuas (Discretizador automático)")
        print("  [3] Cargar batería de pruebas JSON (data/casos_prueba.json)")
        print("  [0] Salir")
        return input("-> Selección: ").strip()

    def _preguntar_estado(self, num: int, etiqueta: str, variable: str) -> Optional[str]:
        estados = VALID_STATES[variable]
        opciones_str = "  ".join([f"[{i+1}] {est}" for i, est in enumerate(estados)])
        print(f"  {num}. {etiqueta:<24}: {opciones_str}  [0] N/D")
        while True:
            sel = input("     -> Selección: ").strip()
            if sel in ("", "0"):
                return None
            if sel.isdigit() and 1 <= int(sel) <= len(estados):
                return estados[int(sel) - 1]
            print("     [!] Opción no válida. Introduzca un número de la lista o 0 para desconocido.")

    def solicitar_discretas(self) -> Dict[str, Optional[str]]:
        print("\nIntroduzca las evidencias observadas (Pulse [0] o Enter si el dato es desconocido):")
        return {
            "galaxia": self._preguntar_estado(1, "Galaxia Anfitriona", "Galaxia_Anfitriona"),
            "ubicacion": self._preguntar_estado(2, "Ubicación Galáctica", "Ubicacion_Galactica"),
            "color": self._preguntar_estado(3, "Color Observado (g-r)", "Color_Observado"),
            "magnitud": self._preguntar_estado(4, "Magnitud Aparente", "Magnitud_Aparente"),
            "anchura_lineas": self._preguntar_estado(5, "Líneas Espectrales", "Anchura_Lineas_Espect"),
            "rayos_x": self._preguntar_estado(6, "Emisión Rayos X", "Emision_RayosX"),
            "curva_luz": self._preguntar_estado(7, "Forma Curva de Luz", "Forma_Curva_Luz"),
        }

    @staticmethod
    def _leer_float_opcional(prompt: str) -> Optional[float]:
        val = input(prompt).strip()
        if not val:
            return None
        return float(val)

    def solicitar_continuas(self) -> Dict[str, float | str | None]:
        print("\nIntroduzca las mediciones instrumentales (Deje en blanco y pulse Enter si no se ha medido):")
        galaxia = self._preguntar_estado(1, "Galaxia Anfitriona", "Galaxia_Anfitriona")
        r_kpc = self._leer_float_opcional("  2. Distancia galactocéntrica r (kpc) [ej. 0.4 Nuclear, 5.0 Brazo, 20.0 Halo]: ")
        g_minus_r = self._leer_float_opcional("  3. Índice de color aparente (g - r) (mag) [ej. -0.2 Azul, 0.2 Neutro, 0.8 Rojo]: ")
        m_v = self._leer_float_opcional("  4. Magnitud aparente óptica m_V (mag) [ej. 15.5 Brillante, 18.0 Interm., 20.5 Débil]: ")
        fwhm_kms = self._leer_float_opcional("  5. Ensanchamiento Doppler FWHM (km/s) [ej. 12000 Anchas, 1500 Estrechas, 0 Ausentes]: ")
        l_x = self._leer_float_opcional("  6. Luminosidad Rayos X L_X (erg/s) [ej. 1e43 Intensa, 1e40 Débil, 0 Nula]: ")
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

    def mostrar_diagnostico(self, resultado: DiagnosisResult, evidencias_activas: Dict[str, str], titulo: str = "") -> None:
        print("\n" + "-" * 74)
        if titulo:
            print(f" CASO: {titulo}")
            print("-" * 74)
        print(f" Evidencias activas: {evidencias_activas if evidencias_activas else 'Ninguna (Distribución A Priori)'}")
        print("-" * 74)
        print(" 1. DISTRIBUCIÓN POSTERIOR DE DIAGNÓSTICO P(Tipo_Transitorio | e)")
        print("-" * 74)

        ordenados = sorted(resultado.probabilidades_transitorio.items(), key=lambda x: x[1], reverse=True)
        for tipo, prob in ordenados:
            bloques = int(round(prob * 30))
            barra = "█" * bloques + "░" * (30 - bloques)
            print(f"  * {tipo:<18} : {barra}  {prob * 100:5.1f} %")

        estado_certeza = "CONCLUYENTE" if resultado.confianza >= 0.70 else "AMBIGUO / REQUIERE SEGUIMIENTO"
        print(f"\n  [DIAGNÓSTICO PRINCIPAL]: {resultado.clase_predicha} "
              f"(Confianza: {resultado.confianza * 100:.1f}% - {estado_certeza} | Entropía H = {resultado.entropia_shannon:.2f} bits)")

        print("\n" + "-" * 74)
        print(" 2. INFERENCIA EXPLICATIVA DE FÍSICA LATENTE (NIVEL 3)")
        print("-" * 74)
        print(f"  * {resultado.generar_explicacion_causal()}")

        print("\n" + "-" * 74)
        print(f" 3. RECOMENDADOR DE SEGUIMIENTO TELESCÓPICO (ENTROPÍA H = {resultado.entropia_shannon:.2f} bits)")
        print("-" * 74)
        if not resultado.recomendacion_seguimiento:
            print("  [OK] Todos los observables están medidos. No se requieren observaciones adicionales.")
        elif resultado.entropia_shannon < 0.20:
            print("  [OK] Diagnóstico de alta certeza (H < 0.20 bits). Seguimiento adicional opcional:")
            top_obs, top_ig = next(iter(resultado.recomendacion_seguimiento.items()))
            print(f"       -> {top_obs} (Ganancia marginal IG = {top_ig:.4f} bits)")
        else:
            for idx, (obs, ig) in enumerate(list(resultado.recomendacion_seguimiento.items())[:3], start=1):
                reduccion_pct = (ig / resultado.entropia_shannon * 100) if resultado.entropia_shannon > 0 else 0.0
                etiqueta = "[RECOMENDADO]" if idx == 1 else "[SECUNDARIO] "
                print(f"  {idx}º {etiqueta} {obs:<22} -> Ganancia esperada IG = {ig:.3f} bits (-{reduccion_pct:.0f}% incertidumbre)")
        print("=" * 74)

    def mostrar_error(self, mensaje: str) -> None:
        print(f"\n[ERROR]: {mensaje}\n")