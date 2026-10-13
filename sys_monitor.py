
import argparse
import csv
import os
import time
from datetime import datetime


# Основні параметри моніторингу системи
INTERVAL = 5       # Інтервал між вимірюваннями, с
TEMP_LIMIT = 60    # Гранична температура процесора, °C
TEMP_PATH = "/sys/class/thermal/thermal_zone0/temp"


# Функція зчитування температури процесора
def get_temperature(path):
    # Отримання температури із системного файлу ядра Linux
    try:
        with open(path, "r") as file:
            # Перетворення значення з міліградусів у градуси Цельсія
            return round(int(file.read().strip()) / 1000, 2)
    except (OSError, ValueError):
        # Повернення None у разі помилки читання або обробки даних
        return None


# Функція отримання статистики роботи процесора
def get_cpu_stats():
    # Зчитування першого рядка /proc/stat із сумарною статистикою CPU
    # split() розділяє рядок на окремі значення за пробілами
    # [1:] пропускає перший елемент "cpu" та залишає числові показники
    # map(int, ...) перетворює отримані рядки на цілі числа
    # list() формує список числових значень для подальших обчислень
    with open("/proc/stat", "r") as file:
        values = list(map(int, file.readline().split()[1:]))

    # Визначення часу простою процесора (idle та iowait)
    idle = values[3] + values[4]

    # Обчислення загального процесорного часу
    total = sum(values)
    return idle, total


# Функція обчислення відсотка завантаження процесора
def get_cpu_usage(previous, current):
    # Визначення зміни часу простою та загального часу CPU
    idle_delta = current[0] - previous[0]
    total_delta = current[1] - previous[1]

    # Перевірка коректності інтервалу вимірювання
    if total_delta <= 0:
        return 0.0

    # Обчислення завантаження CPU за різницею двох вимірювань
    return round(100 * (1 - idle_delta / total_delta), 2)


# Функція визначення використання оперативної пам'яті
def get_ram_usage():
    # Створення порожнього словника для збереження параметрів RAM
    # Ключами будуть назви параметрів, а значеннями — обсяг пам'яті
    memory = {}

    # Отримання параметрів пам'яті із системного файлу /proc/meminfo
    with open("/proc/meminfo", "r") as file:
        for line in file:
            # Формування словника з назвами та значеннями параметрів
            # Розділення рядка за першим символом ":"
            # key містить назву параметра, value — його числове значення з одиницею вимірювання
            key, value = line.split(":", 1)

            # Видалення зайвих пробілів та відокремлення числа від одиниці "kB"
            # Перетворення числа на тип int і збереження у словнику за відповідним ключем
            memory[key] = int(value.strip().split()[0])

    # Визначення загального та доступного обсягу оперативної пам'яті
    total = memory["MemTotal"]
    available = memory["MemAvailable"]

    # Обчислення відсотка використаної оперативної пам'яті
    return round(100 * (total - available) / total, 2)


# Основна функція керування процесом моніторингу
def main():
    # Налаштування аргументів командного рядка
    # Створення об'єкта для обробки аргументів командного рядка
    parser = argparse.ArgumentParser()

    # Кількість вимірювань (0 — необмежена кількість)
    parser.add_argument("--count", type=int, default=0)

    # Інтервал між вимірюваннями в секундах (за замовчуванням 5 с)
    parser.add_argument("--interval", type=float, default=INTERVAL)

    # Назва файлу для збереження результатів моніторингу
    parser.add_argument("--output", default="telemetry.csv")

    # Шлях до системного файлу температури процесора
    parser.add_argument("--temp-path", default=TEMP_PATH)

    # Зчитування переданих аргументів та збереження їхніх значень
    args = parser.parse_args()

    # Перевірка допустимості заданого інтервалу вимірювань
    if args.interval <= 0:
        parser.error("Інтервал має бути більше нуля")

    # Перевірка наявності CSV-файлу та необхідності створення заголовка
    file_exists = os.path.exists(args.output)
    needs_header = not file_exists or os.path.getsize(args.output) == 0

    # Отримання початкових значень статистики процесора
    previous = get_cpu_stats()
    count = 0

    # Відкриття CSV-файлу в режимі додавання нових записів
    with open(args.output, "a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        # Запис назв стовпців під час створення нового файлу
        if needs_header:
            writer.writerow([
                "Timestamp", "Temp", "CPU_Load", "RAM_Usage"
            ])
            file.flush()

        print("Моніторинг системи запущено")

        try:
            # Безперервний моніторинг або виконання заданої кількості циклів
            while args.count == 0 or count < args.count:
                # Очікування встановленого інтервалу між вимірюваннями
                time.sleep(args.interval)

                # Отримання поточної статистики та завантаження CPU
                current = get_cpu_stats()
                cpu = get_cpu_usage(previous, current)
                previous = current

                # Зчитування використання RAM і температури процесора
                ram = get_ram_usage()
                temp = get_temperature(args.temp_path)

                # Формування часової позначки з урахуванням часового поясу
                timestamp = datetime.now().astimezone().isoformat(
                    timespec="seconds"
                )

                # Обробка випадку недоступності температурного датчика
                temp_value = temp if temp is not None else "N/A"

                # Збереження отриманих показників у CSV-файл
                writer.writerow([
                    timestamp, temp_value, cpu, ram
                ])

                # Примусове збереження буферизованих даних у файл
                file.flush()

                # Виведення поточних показників у консоль
                print(
                    f"{timestamp} | Temp: {temp_value} °C | "
                    f"CPU: {cpu}% | RAM: {ram}%"
                )

                # Перевірка перевищення граничної температури процесора
                if temp is not None and temp > TEMP_LIMIT:
                    print("УВАГА: перевищено температурний поріг!")

                # Збільшення лічильника виконаних циклів моніторингу
                count += 1

        # Коректне завершення моніторингу за командою користувача
        except KeyboardInterrupt:
            print("\nМоніторинг зупинено")


# Точка входу в програму під час безпосереднього запуску скрипта
if __name__ == "__main__":
    main()
