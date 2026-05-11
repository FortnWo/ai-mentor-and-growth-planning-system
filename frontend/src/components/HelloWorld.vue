<script setup lang="ts">
import { ref } from 'vue'

const count = ref(0)
</script>

<template>
  <div class="hello-world-root">
    <section id="center">
      <div class="hero">
        <img src="../assets/hero.png" class="base" width="170" height="179" alt="" />
        <img src="../assets/vue.svg" class="framework" alt="Vue logo" />
        <img src="../assets/vite.svg" class="vite" alt="Vite logo" />
      </div>
      <div>
        <h1>开始使用</h1>
        <p>编辑 <code>src/App.vue</code> 并保存即可测试 <code>HMR</code></p>
      </div>
      <button class="counter" @click="count++">点击次数：{{ count }}</button>
    </section>

    <div class="ticks"></div>

    <section id="next-steps">
      <div id="docs">
        <svg class="icon" role="presentation" aria-hidden="true">
          <use href="/icons.svg#documentation-icon"></use>
        </svg>
        <h2>文档</h2>
        <p>常见问题与说明</p>
        <ul>
          <li>
            <a href="https://vite.dev/" target="_blank">
              <img class="logo" src="../assets/vite.svg" alt="" />
              浏览 Vite
            </a>
          </li>
          <li>
            <a href="https://vuejs.org/" target="_blank">
              <img class="button-icon" src="../assets/vue.svg" alt="" />
              了解更多
            </a>
          </li>
        </ul>
      </div>
      <div id="social">
        <svg class="icon" role="presentation" aria-hidden="true">
          <use href="/icons.svg#social-icon"></use>
        </svg>
        <h2>关注我们</h2>
        <p>加入 Vite 社区</p>
        <ul>
          <li>
            <a href="https://github.com/vitejs/vite" target="_blank">
              <svg class="button-icon" role="presentation" aria-hidden="true">
                <use href="/icons.svg#github-icon"></use>
              </svg>
              GitHub
            </a>
          </li>
          <li>
            <a href="https://chat.vite.dev/" target="_blank">
              <svg class="button-icon" role="presentation" aria-hidden="true">
                <use href="/icons.svg#discord-icon"></use>
              </svg>
              Discord
            </a>
          </li>
          <li>
            <a href="https://x.com/vite_js" target="_blank">
              <svg class="button-icon" role="presentation" aria-hidden="true">
                <use href="/icons.svg#x-icon"></use>
              </svg>
              X.com
            </a>
          </li>
          <li>
            <a href="https://bsky.app/profile/vite.dev" target="_blank">
              <svg class="button-icon" role="presentation" aria-hidden="true">
                <use href="/icons.svg#bluesky-icon"></use>
              </svg>
              Bluesky
            </a>
          </li>
        </ul>
      </div>
    </section>

    <div class="ticks"></div>
    <section id="spacer"></section>
  </div>
</template>
