<script setup lang="ts">
import { Clapperboard, Code2, Presentation } from '@lucide/vue'
import type { Cover, WorkKind } from '../works'

defineProps<{ cover?: Cover; kind: WorkKind }>()
const icons = { slides: Presentation, video: Clapperboard, source: Code2 }
</script>

<template>
  <div class="work-art" :class="cover ? 'art-' + cover : 'art-local art-local-' + kind" aria-hidden="true">
    <component v-if="!cover" :is="icons[kind]" :size="50" :stroke-width="1.35" />
  </div>
</template>
