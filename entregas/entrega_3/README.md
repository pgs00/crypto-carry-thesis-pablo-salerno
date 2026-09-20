# Entrega 3

La entrega vigente corresponde a **dos carteras continuas del 01/01/2022 al
31/08/2026 UTC**, con `futures_scaled`, sin reinicios anuales.

- [Resultados, tablas y figuras para consultar en GitHub](continua/README.md).
- [Paquete vigente completo](paquete_actualizacion_entrega_3_continua.zip)
  (9,64 MB) y [SHA-256](paquete_actualizacion_entrega_3_continua.zip.sha256).
  Conserva las corridas verificadas; no contiene datos masivos de Binance.
- [Anexo posterior: sensibilidad del precio de funding](../../data/research/funding-price-sensitivity-20260920/README.md).
  Este anexo se publica por separado y no altera el ZIP sellado.
- [Archivo de las ventanas independientes](archivo/README.md): antecedentes,
  versiones originales y verificadores preservados.

Desde la raíz del repositorio, `python -m scripts.publish_thesis --verify`
comprueba la vista publicada y su correspondencia con el ZIP vigente. El
`verificar.py` incluido en el ZIP comprueba el paquete completo una vez extraído.
La [guía principal](../../README.md#reproducción) distingue estas verificaciones
de los análisis que requieren fuentes locales.
