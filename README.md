# SIPL Language Toolkit

[![CI](https://github.com/tiulenchik2/sipl-tp-project/actions/workflows/ci.yml/badge.svg)](https://github.com/tiulenchik2/sipl-tp-project/actions/workflows/ci.yml)

Модульний набір інструментів для мови програмування **SIPL (SImple Programming Language)** у межах курсу "Теорія програмування": формальна граматика, типізоване AST із `SourceSpan`, інтерпретатор із подійним трасуванням, CLI з JSON-контрактом, візуалізація дерева синтаксичного виводу та автоматична побудова семантичних термів.

## Обраний набір завдань (Заявлений скоуп)

Сума виконаних модулів — **10.5 бала** (підсумкова оцінка за проєкт обмежується **10.0 балами**).

| ID | Модуль | Бали | Статус |
| :--- | :--- | :---: | :--- |
| **CORE-01** | Формальна специфікація SIPL (Lark/EBNF), опис лексики, позитивні/негативні тести | 0.5 | Виконано (`v0.1.0`) |
| **CORE-02** | Парсер і типізоване AST із позиціями `SourceSpan` та діагностиками помилок | 1.5 | Виконано (`v0.1.0`) |
| **CORE-03** | Інтерпретатор SIPL із лімітом кроків та покриттям ядра тестами $\ge 80\%$ | 2.0 | Виконано (`v0.2.0`) |
| **CORE-04** | Подієва модель виконання та trace у JSON (`Before/AfterStatement`, зміна змінної, умова, завершення) | 1.0 | Виконано (`v0.2.0`) |
| **CORE-05** | CLI (`parse`, `check`, `run`, `trace`) зі стабільною JSON-схемою та інтеграційними тестами | 1.0 | Виконано (`v0.3.0`) |
| **VIS-01** | Візуалізація дерева синтаксичного виводу (`Text` + `JSON` + `DOT`/`SVG`) із прив’язкою до коду | 1.5 | Виконано (`v0.4.0`) |
| **SEM-01** | Рекурсивна побудова семантичного терму з AST у нотації курсу + golden tests | 2.0 | Виконано (`v0.5.0`) |
| **REL-01** | CI у GitHub Actions (`ruff`, `mypy`, `pytest --cov`, `build`) на кожен PR | 0.5 | Виконано (`v0.1.0`) |
| **REL-02** | GitHub Releases + SemVer + `CHANGELOG.md` з артефактами збірки | 0.5 | Виконано (`v1.0.0`) |
| **Разом** | **9 модулів (у залік до 10.0)** | **10.5** | **Готово** |

## Архітектура проєкту

Ядро мови реалізоване як незалежна Python-бібліотека (`src/sipl/`) зі стабільними моделями даних (`SourceSpan`, `Diagnostic`, типізоване AST, `ExecutionResult`, `ParseTreeNode`, `SemanticTerm`). CLI, візуалізатор і генератор семантичних термів перевикористовують спільний парсер та AST без дублювання логіки.

```text
sipl-tp-project/
├── grammar/sipl.lark           # Формальна граматика SIPL (Lark/EBNF)
├── src/sipl/
│   ├── ast.py                  # Типізовані AST-вузли із SourceSpan
│   ├── diagnostics.py          # SourceSpan, Diagnostic, винятки
│   ├── parser.py               # Парсер (parse_tree, parse, check_syntax)
│   ├── interpreter/            # Інтерпретатор та події trace
│   ├── visualization/          # Експортери Parse Tree (Text, JSON, DOT, SVG)
│   ├── semantics/              # Конструктор семантичних термів та форматер
│   └── cli.py                  # CLI-інтерфейс (sipl / python -m sipl)
├── examples/                   # Приклади SIPL-програм (pow, gcd, div)
├── docs/                       # Специфікація граматики (grammar.md) та CLI (cli.md)
├── tests/                      # Unit-, інтеграційні та golden-тести
└── CHANGELOG.md                # Історія релізів (SemVer)
```

## Встановлення (з чистого середовища)

Вимоги: **Python 3.10+**.

### Варіант 1. Встановлення з вихідного коду (для розробки та запуску тестів)

```bash
git clone https://github.com/tiulenchik2/sipl-tp-project.git
cd sipl-tp-project

python -m venv .venv
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

pip install --upgrade pip
pip install -e ".[dev]"
```

### Варіант 2. Встановлення з релізного артефакту (`.whl`)

```bash
pip install sipl_toolkit-1.0.0-py3-none-any.whl
```

## Використання CLI

Після встановлення доступна команда `sipl` (або `python -m sipl`). Замість шляху до файлу можна передати `-`, щоб прочитати код зі `stdin`.

Детальна специфікація команд, кодів завершення та JSON-схеми (`schema_version = "1.0"`) наведена в [`docs/cli.md`](docs/cli.md), а формальний опис синтаксису та лексики — у [`docs/grammar.md`](docs/grammar.md).

```bash
# Синтаксична перевірка
sipl check examples/pow.sipl --json

# Побудова типізованого AST із SourceSpan
sipl parse examples/pow.sipl --json

# Виконання програми з початковим станом змінних
sipl run examples/pow.sipl --var X=5 --var Y=2
sipl run examples/gcd.sipl --state '{"M": 8, "N": 16}' --json

# Покроковий trace виконання у JSON
sipl trace examples/div.sipl --var X=7 --var Y=4 --max-steps 1000 --json

# Візуалізація дерева синтаксичного виводу (text | json | dot | svg)
sipl tree examples/pow.sipl --format text
sipl tree examples/pow.sipl --format dot --output pow.dot
sipl tree examples/pow.sipl --format svg --output pow.svg

# Побудова семантичного терму в нотації курсу (або ASCII)
sipl sem examples/pow.sipl --steps
sipl sem examples/gcd.sipl --style ascii --json
```

### Приклад SIPL-програми (`examples/pow.sipl`)

Обчислення $x^y$ для $x, y > 0$:

```text
begin
  R := 1;
  while Y > 0 do
    begin
      R := R * X;
      Y := Y - 1
    end
end
```

## Тестування та перевірка якості

```bash
ruff check .
mypy src tests
pytest -v --cov=sipl --cov-report=term-missing --cov-fail-under=80
python -m build
```

## Специфікація та обмеження

* **Граматика:** реалізовано базовий синтаксис SIPL за БНФ курсу (`begin/end`, `:=`, `;`, `if/then/else`, `while/do`, `skip`, арифметика `+`, `-`, `*`, порівняння `=`, `>`, логіка `¬`/`not`, `∨`/`or`) із фіксованими пріоритетами та лівоасоціативністю бінарних операцій.
* **Типи даних:** підтримуються лише цілі числа (`Int`) та булеві умови (`Bool`) без явної типізації змінних.
* **Обробка невизначеності:** використовується строга семантика часткових функцій; звернення до неініціалізованої змінної повертає діагностику `E2001` (`UndefinedVariableError`) із точним `SourceSpan`.
* **Захист від нескінченних циклів:** інтерпретатор контролює максимальну кількість кроків (`--max-steps`, за замовчуванням `10000`) і коректно зупиняє виконання з кодом помилки `E2002` (`StepLimitExceededError`).
* **Межі автоматизації:** модуль `SEM-01` будує семантичний терм і трасу застосованих правил переписування (`NS_*`), але не виконує автоматичне формальне доведення коректності циклів.

## Цикл версій

Повна історія змін зафіксована у [`CHANGELOG.md`](CHANGELOG.md):

* `v0.1.0` — Граматика SIPL, типізоване AST, парсер та CI (`CORE-01`, `CORE-02`, `REL-01`)
* `v0.2.0` — Інтерпретатор та подієвий trace (`CORE-03`, `CORE-04`)
* `v0.3.0` — CLI, JSON-контракт та інтеграційні тести (`CORE-05`)
* `v0.4.0` — Візуалізація Parse Tree у Text/JSON/DOT/SVG (`VIS-01`)
* `v0.5.0` — Рекурсивна побудова семантичних термів та golden tests (`SEM-01`)
* `v1.0.0` — Стабілізація контрактів, документація та GitHub Release (`REL-02`)