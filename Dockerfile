FROM python:3.11-slim

# Tashkent vaqt mintaqasi va Python parametrlarini o'rnatish
ENV TZ=Asia/Tashkent \
    DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Tizim paketlari va vaqt mintaqasini yangilash
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    curl \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# Kutubxonalarni o'rnatish
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Loyiha fayllarini nusxalash
COPY . .

# Root huquqisiz ishlash: bot buzilsa ham konteyner ichida root bo'lmaydi
RUN useradd --create-home --uid 10001 smena && mkdir -p /app/logs && chown -R smena /app/logs
USER smena

# Botni ishga tushirish
CMD ["python", "bot.py"]
