/// <reference types="vite/client" />

declare module '*.vue' {
    import type { DefineComponent } from 'vue'

    const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>
    export default component
}

// 图片与字体等静态资源声明
declare module '*.png'
declare module '*.jpg'
declare module '*.jpeg'
declare module '*.gif'
declare module '*.svg'
declare module '*.webp'