import { defineConfig, presetUno, presetAttributify } from 'unocss'

export default defineConfig({
  presets: [
    presetUno(),
    presetAttributify(),
  ],
  shortcuts: {
    'btn': 'px-4 py-2 rounded-xl inline-flex justify-center items-center font-medium bg-indigo-600 text-white cursor-pointer hover:bg-indigo-700 transition-all shadow-sm active:scale-98',
    'center': 'flex justify-center items-center',
    'glass': 'bg-white/80 backdrop-blur-md border border-white/60 shadow-sm',
    'glass-dark': 'bg-slate-900/80 backdrop-blur-md border border-white/10 shadow-lg',
    'card-hover': 'transition-all duration-300 hover:translate-y-[-2px] hover:shadow-lg',
  },
  theme: {
    colors: {
      brand: {
        50: '#eef2ff',
        100: '#e0e7ff',
        200: '#c7d2fe',
        300: '#a5b4fc',
        400: '#818cf8',
        500: '#6366f1',
        600: '#4f46e5',
        700: '#4338ca',
        800: '#3730a3',
        900: '#312e81',
      }
    }
  }
})
