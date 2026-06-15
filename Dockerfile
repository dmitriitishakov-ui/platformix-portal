# Берём готовый образ с Python 3.12
FROM python:3.12-slim

# Рабочая папка внутри контейнера
WORKDIR /app

# Сначала копируем только зависимости и ставим их
# (так Docker кэширует слой и не переустанавливает при каждом изменении кода)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем остальной код проекта
COPY . .

# Порт, на котором работает приложение
EXPOSE 8080

# Команда запуска
CMD ["python", "app.py"]
