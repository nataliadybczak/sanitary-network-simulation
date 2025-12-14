# sanitary-network-simulation - Symulacja Sieci Kanalizacyjnej

Projekt ten symuluje działanie sieci kanalizacyjnej, modelując przepływ ścieków, wpływ opadów atmosferycznych oraz obciążenie oczyszczalni w czasie rzeczywistym. Aplikacja oferuje graficzny interfejs z mapą i wykresami, pozwalając na monitorowanie stanu czujników, przelewów burzowych i intensywności deszczu. Użytkownik może dynamicznie sterować prędkością symulacji oraz testować różne scenariusze pogodowe i parametry infrastuktury.

##  Instalacja i Konfiguracja

Aby uruchomić projekt, wykonaj poniższe kroki.

### 1. Instalacja Python 3.13.2

Projekt wymaga konkretnej wersji Pythona.

1.  Wejdź na oficjalną stronę Python: [Pobierz Python 3.13.2](https://www.python.org/downloads/release/python-3132/).
2.  Pobierz instalator odpowiedni dla Twojego systemu operacyjnego (Windows/macOS/Linux).
3.  **Ważne (Windows):** Podczas instalacji koniecznie zaznacz opcję **"Add Python to PATH"** (Dodaj Python do zmiennych środowiskowych) przed kliknięciem "Install Now".

### 2. Tworzenie Wirtualnego Środowiska (venv)

Zaleca się instalację pakietów w izolowanym środowisku, aby uniknąć konfliktów. Otwórz terminal (lub wiersz poleceń) w folderze projektu i wpisz:

**Windows:**
```bash
python -m venv venv
.\venv\Scripts\activate
```
**MacOS / Linux:**

```bash
python3.13 -m venv venv
source venv/bin/activate
```
(Po poprawnej aktywacji powinieneś widzieć (venv) na początku linii w terminalu).

### 3. Instalacja Wymaganych Pakietów

Mając aktywne środowisko wirtualne, zainstaluj zależności z pliku requirements.txt:

```bash
pip install -r requirements.txt
```

## Uruchamianie Symulacji
Symulację uruchamia się za pomocą pliku run_visualisation.py. Możesz uruchomić ją w trybie domyślnym lub spersonalizować parametry startowe.

## Dostępne parametry uruchomienia

### Skrypt przyjmuje następujące argumenty (opcjonalne):

**--interval_sec (float)**: Szybkość symulacji. Określa, co ile sekund czasu rzeczywistego następuje aktualizacja godziny w symulacji. Mniejsza liczba = szybsza symulacja. Domyślnie: 0.5.

**--rain_file (str)**: Scenariusz opadowy. Ścieżka do pliku CSV zawierającego dane o intensywności deszczu. Domyślnie: data/rain.csv.

**--max_hours (int)**: Długość symulacji. Liczba godzin symulacyjnych, po których program zakończy działanie. Domyślnie: 168 (tydzień).

**--max_capacity (int)**: Przepustowość oczyszczalni. Maksymalna ilość ścieków (m³/h), którą oczyszczalnia może przyjąć przed wystąpieniem awarii/przepełnienia. Domyślnie: 2000.

## Przykłady użycia

1. Uruchomienie domyślne: Najprostszy sposób. Używa standardowych ustawień z kodu (interwał 0.5s, domyślny deszcz).

```bash
python run_visualisation.py
```

2. Własny plik deszczu i krótszy czas: Użycie innego pliku z danymi (np. silna ulewa) i symulacja trwająca tylko 24 godziny.

```bash
python run_visualisation.py --rain_file data/rain_experiments/extreme.csv --max_hours 50
```