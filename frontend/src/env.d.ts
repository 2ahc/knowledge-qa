// Vite 环境类型声明：让 TypeScript 认识 .vue 单文件组件的默认导出。
/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
