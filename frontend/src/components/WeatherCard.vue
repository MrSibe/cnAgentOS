<template>
  <div class="weather-card" :class="bgClass">
    <div class="weather-city">{{ weather.city }}</div>
    <div class="weather-temp">{{ weather.temp_c }}°C</div>
    <div class="weather-desc">{{ weather.weather_desc }}</div>
    <div class="weather-details">
      <div class="detail-item">
        <span class="detail-label">湿度</span>
        <span class="detail-value">{{ weather.humidity }}%</span>
      </div>
      <div class="detail-item">
        <span class="detail-label">风向</span>
        <span class="detail-value">{{ weather.wind_dir }}</span>
      </div>
      <div class="detail-item">
        <span class="detail-label">风速</span>
        <span class="detail-value">{{ weather.wind_speed_kmph }} km/h</span>
      </div>
      <div class="detail-item">
        <span class="detail-label">体感</span>
        <span class="detail-value">{{ weather.feels_like_c }}°C</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  weather: {
    city: string
    temp_c: string
    humidity: string
    weather_desc: string
    wind_dir: string
    wind_speed_kmph: string
    feels_like_c?: string
  }
}>()

const bgClass = computed(() => {
  const desc = (props.weather.weather_desc || '').toLowerCase()
  if (desc.includes('sun') || desc.includes('clear') || desc.includes('晴')) return 'weather-sunny'
  if (desc.includes('rain') || desc.includes('drizzle') || desc.includes('雨')) return 'weather-rainy'
  if (desc.includes('cloud') || desc.includes('overcast') || desc.includes('阴') || desc.includes('云')) return 'weather-cloudy'
  if (desc.includes('snow') || desc.includes('雪')) return 'weather-snowy'
  if (desc.includes('fog') || desc.includes('雾')) return 'weather-foggy'
  return 'weather-default'
})
</script>

<style scoped>
.weather-card {
  border-radius: 12px;
  padding: 16px;
  color: white;
  margin: 8px 0;
  max-width: 280px;
}
.weather-sunny { background: linear-gradient(135deg, #f093fb, #f5576c); }
.weather-rainy { background: linear-gradient(135deg, #4facfe, #00f2fe); }
.weather-cloudy { background: linear-gradient(135deg, #a8c0ff, #3f2b96); }
.weather-snowy { background: linear-gradient(135deg, #e6dada, #274046); }
.weather-foggy { background: linear-gradient(135deg, #d7d2cc, #304352); }
.weather-default { background: linear-gradient(135deg, #667eea, #764ba2); }
.weather-city { font-size: 18px; font-weight: bold; margin-bottom: 4px; }
.weather-temp { font-size: 36px; font-weight: bold; margin: 8px 0; }
.weather-desc { font-size: 14px; opacity: 0.9; margin-bottom: 12px; }
.weather-details { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.detail-item { display: flex; flex-direction: column; }
.detail-label { font-size: 11px; opacity: 0.7; }
.detail-value { font-size: 14px; font-weight: 500; }
</style>
