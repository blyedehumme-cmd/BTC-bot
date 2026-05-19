# Lesly AI Trading — Future Architecture

## Visión general

Lesly es una plataforma de trading automatizado con UI premium, enfocada inicialmente en paper trading. El frontend actual es una landing page y dashboard visual construido con Next.js, React y Tailwind CSS.

La arquitectura futura estará basada en:

- Frontend: Next.js + React + Tailwind CSS
- Backend: Python FastAPI
- Base de datos: PostgreSQL
- IA: módulos de análisis textual, análisis visual, scoring de señales y aprendizaje histórico
- Integración futura: Coinbase en modo de solo lectura / paper trading, sin órdenes reales activas

## Estructura de carpetas sugerida

```
lesly-frontend/
  app/
    globals.css
    layout.tsx
    page.tsx
  components/
    Hero.tsx
    TradingPanel.tsx
    FeatureCards.tsx
    AiLogs.tsx
    Footer.tsx
  package.json
  tsconfig.json
  tailwind.config.ts
  postcss.config.js
  next-env.d.ts
  README.md
  ARCHITECTURE.md

backend/
  app/
    main.py
    api/
      routes.py
      signals.py
      ai_status.py
    services/
      market_data.py
      signal_engine.py
      risk_engine.py
      ai_learning.py
    models/
      schemas.py
      database.py
    core/
      settings.py
      security.py
  alembic/
  requirements.txt
  Dockerfile

database/
  init.sql
  migrations/

shared/
  schemas/
    dto.py
    events.py
  utils/
    constants.py
    logger.py
```

## Modelos de datos iniciales

### signals

- id
- symbol
- timeframe
- direction
- confidence_score
- risk_level
- market_condition
- created_at
- approved
- explanation
- paper_mode

### trades_paper

- id
- signal_id
- entry_price
- stop_loss
- take_profit
- target_price
- closed_price
- result_pct
- status
- opened_at
- closed_at
- drawdown_pct
- notes

### ai_decisions

- id
- signal_id
- decision_type
- reason
- condition_snapshot
- explanation
- timestamp

### market_snapshots

- id
- symbol
- timeframe
- candle_open
- candle_high
- candle_low
- candle_close
- volume
- indicators
- pattern_analysis
- created_at

### strategy_performance

- id
- timeframe
- total_signals
- wins
- losses
- win_rate
- average_return
- max_drawdown
- last_updated

### rejected_signals

- id
- signal_id
- reject_reason
- rejection_score
- conditions
- timestamp

### learning_notes

- id
- signal_id
- metric
- observation
- improvement_action
- created_at

## Cómo aprendería la IA

La IA futura seguirá un ciclo de aprendizaje cerrado:

1. Recolecta datos del mercado y snapshots multitimeframe.
2. Genera señales simuladas en paper trading.
3. Registra condiciones de mercado, indicadores y contexto.
4. Almacena resultados simulados y métricas de performance.
5. Analiza qué configuraciones dieron mejores resultados.
6. Ajusta filtros, pesos y scoring de señales.
7. Produce explicaciones para cada decisión.

### Datos recolectados por señal

- condiciones antes de la señal
- indicadores usados
- timeframe principal
- precio de entrada simulado
- stop loss simulado
- take profit simulado
- resultado simulado
- drawdown
- señal buena/mala
- razón de la decisión
- comentario de IA

## Flujo de decisión propuesto

1. `market_data` ingresa velas, volumen y estructura de mercado.
2. `signal_engine` genera un conjunto inicial de oportunidades.
3. `ai_analysis` evalúa patrones, momentum y soporte/resistencia.
4. `risk_engine` filtra señales con bajo volumen, lateralidad o alto drawdown.
5. `scoring_module` asigna confianza y riesgo.
6. `decision_module` aprueba o rechaza en paper trading.
7. Todo queda registrado en `signals`, `ai_decisions` y `market_snapshots`.
8. `learning_module` analiza resultados históricos y actualiza pesos.

## Componentes de IA futura

- `analysis_textual`: explica en lenguaje natural por qué la señal fue aprobada o rechazada.
- `analysis_visual`: interpreta gráficos de velas, soportes, resistencias y momentum.
- `scoring_signals`: asigna score de confianza basado en múltiples factores.
- `learning_history`: aprende de resultados previos y ajusta reglas.
- `explanation_engine`: genera mensajes claros para el usuario.

## Seguridad y reglas de protección

- Modo real bloqueado por defecto.
- No hay permisos de retiro de fondos.
- Las claves de API deben cifrarse y almacenarse fuera del código.
- Solo paper trading hasta que el usuario active manualmente un modo real en el futuro.
- Reglas de protección:
  - No operar en noticias extremas.
  - No operar en mercado lateral.
  - No operar con baja liquidez.
  - No operar tras pérdidas consecutivas.
  - No aumentar riesgo automáticamente.
  - No usar leverage alto.
  - Priorizar preservación de capital.

## Qué construir ahora y qué dejar para después

### Construir ahora

- UI visual premium en Next.js (ya implementado).
- Landing page y dashboard simulado.
- Componentes visuales para señales, estadísticas y logs.
- Documentación de arquitectura.
- Modo paper trading como estado visible.

### Dejar para después

- Backend FastAPI funcional.
- Conexión real a Coinbase.
- Ejecución de órdenes reales.
- Almacenamiento en PostgreSQL.
- Módulos avanzados de IA y aprendizaje automático.
- Análisis visual real de gráficos.
- Autenticación y gestión de API keys.

## Conclusión

La implementación actual ya provee el frontend mockup y la base para una arquitectura escalable. El siguiente paso ideal es desarrollar el backend FastAPI, diseñar la base de datos PostgreSQL y construir el motor de señales en paper trading con capacidades de aprendizaje.
