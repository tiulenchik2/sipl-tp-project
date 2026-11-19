# Changelog

Усі помітні зміни в проєкті **SIPL Language Toolkit** документуються в цьому файлі.
Формат відповідає [Keep a Changelog](https://keepachangelog.com/uk/1.1.0/), а версіонування — [Semantic Versioning](https://semver.org/).


## [1.0.0] - 2026-11-19

### Changed
- Зафіксовано стабільний публічний API бібліотеки `sipl` та JSON-контракт CLI (`schema_version = "1.0"`).
- Оновлено `README.md` з повними інструкціями встановлення, прикладами всіх команд CLI та матрицею виконаних модулів.
- Додано `CHANGELOG.md` та підготовлено релізні артефакти (`.whl`, `.tar.gz`).

## [0.5.0] - 2026-11-19

### Added
- **SEM-01:** Рекурсивна побудова семантичного терму з AST у нотації курсу (`src/sipl/semantics/`) із трасуванням застосованих правил (`NS_Prog`, `NS_Stm_*`, `NS_A_*`, `NS_B_*`).
- Форматування термів у курсову Unicode-нотацію (`course`) та `ascii`.
- CLI-підкоманда `sipl sem` (`--style`, `--steps`, `--json`) і golden tests для `pow.sipl`, `gcd.sipl`, `div.sipl`.

## [0.4.0] - 2026-11-19

### Added
- **VIS-01:** Візуалізація дерева синтаксичного виводу (`src/sipl/visualization/`) у форматах `Text`, `JSON`, `DOT` та автономний `SVG` із прив’язкою кожного вузла до `SourceSpan` і нумерацією термінальних листків.
- CLI-підкоманда `sipl tree` (`--format`, `--output`, `--json`) та тести візуалізації.

## [0.3.0] - 2026-11-19

### Added
- **CORE-05:** CLI-інтерфейс `sipl` / `python -m sipl` із командами `parse`, `check`, `run`, `trace`.
- Стабільна JSON-схема (`schema_version = "1.0"`), фіксовані коди завершення (`0`, `2`, `3`, `4`, `5`), підтримка `stdin` (`-`), документація `docs/cli.md` та інтеграційні тести.

## [0.2.0] - 2026-11-19

### Added
- **CORE-03:** Tree-walking інтерпретатор SIPL (`src/sipl/interpreter/engine.py`) із контролем ліміту кроків (`StepLimitExceededError`) та явною перевіркою невизначених змінних (`UndefinedVariableError`).
- **CORE-04:** Подієва модель виконання (`BeforeStatement`, `AfterStatement`, `VarChanged`, `ConditionChecked`, `Finished`) з підтримкою callback-підписника та JSON-серіалізацією.
- Контроль покриття коду тестами $\ge 80\%$ у GitHub Actions CI.

## [0.1.0] - 2026-11-19

### Added
- **CORE-01:** Машинозчитувана граматика `grammar/sipl.lark` (Lark/EBNF), специфікація лексики й пріоритетів `docs/grammar.md`, приклади `examples/{pow,gcd,div}.sipl` та $\ge 10$ позитивних і $\ge 10$ негативних тестів.
- **CORE-02:** Моделі `SourceSpan`, `Diagnostic` і типізоване AST (`src/sipl/ast.py`), парсер (`src/sipl/parser.py`) з точними координатами синтаксичних помилок.
- **REL-01:** Базовий каркас пакета та GitHub Actions CI (`ruff`, `mypy`, `pytest`, `build`).