# SIPL CLI Reference

Точка входу встановлюється як команда `sipl` (або `python -m sipl`).

## Команди

| Команда | Призначення | Приклад |
| :--- | :--- | :--- |
| `sipl parse <file> [--json]` | Побудова типізованого AST із `SourceSpan` | `sipl parse examples/pow.sipl --json` |
| `sipl check <file> [--json]` | Синтаксична перевірка та діагностики | `sipl check examples/gcd.sipl --json` |
| `sipl run <file> [--var K=V ...] [--state JSON] [--max-steps N] [--json]` | Виконання програми та вивід фінального стану | `sipl run examples/pow.sipl --var X=5 --var Y=2` |
| `sipl trace <file> [--var K=V ...] [--state JSON] [--max-steps N] [--json]` | Виконання з повним логом подій trace | `sipl trace examples/div.sipl --var X=7 --var Y=4 --json` |

Замість шляху до файлу можна передати `-` для читання SIPL-коду зі `stdin`.

## Коди завершення (Exit Codes)

| Код | Значення |
| :---: | :--- |
| `0` | Успішне виконання команди |
| `2` | Помилка аргументів CLI, формату `--var`/`--state` або читання файлу |
| `3` | Лексична або синтаксична помилка SIPL (`E1xxx`) |
| `4` | Помилка часу виконання, зокрема невизначена змінна (`E2001`) |
| `5` | Перевищення ліміту кроків виконання (`E2002`) |

## Стабільна JSON-схема (`schema_version = "1.0"`)

Кожна відповідь із прапорцем `--json` містить базову оболонку:

```json
{
  "schema_version": "1.0",
  "command": "parse | check | run | trace",
  "ok": true,
  "exit_code": 0
}
```
- `parse` (успіх): додає `"ast": { "kind": "Program", ... }`.
- `check` (успіх/помилка): додає `"diagnostics": [ ... ]`.
- `run` (успіх): додає `"status": "completed", "steps": <int>, "state": { "<var>": <int> }`.
- `trace` (успіх): додає всі поля `run` плюс `"events": [ ... ]`.
- Помилки синтаксису / виконання: `"ok": false`, відповідний `"exit_code"` (`3`, `4` або `5`) та масив `"diagnostics"`; для trace при runtime-помилці також повертаються `"events"`, зафіксовані до моменту збою.
- Помилка вводу/аргументів (`exit_code = 2`): `"ok": false, "error": "<message>"`.