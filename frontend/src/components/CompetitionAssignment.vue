<script setup lang="ts">
import { computed, watch } from 'vue'
import { ChevronDown } from '@lucide/vue'
import type { Competition } from '../works'

const props = defineProps<{ competitions: Competition[]; disabled?: boolean }>()
const competition = defineModel<number | null>('competition', { required: true })
const year = defineModel<number | null>('year', { required: true })
const current = computed(() => props.competitions.find(item => item.id === competition.value))
const years = computed(() => current.value?.years ?? [])

watch(years, available => {
  if (current.value && year.value !== null && !available.includes(year.value)) year.value = null
})
</script>

<template>
  <div class="upload-work-details">
    <label class="form-field">
      <span>比赛分类</span>
      <span class="attachment-select">
        <select v-model="competition" :disabled="disabled" @change="year = null">
          <option :value="null">未分类</option>
          <option v-for="item in competitions" :key="item.id" :value="item.id">{{ item.name }}</option>
        </select>
        <ChevronDown :size="16" aria-hidden="true" />
      </span>
    </label>
    <label class="form-field">
      <span>比赛年份</span>
      <span class="attachment-select">
        <select v-model="year" :disabled="disabled || !years.length">
          <option :value="null">{{ !competition ? '请先选择比赛' : years.length ? '未标注年份' : '暂无可选年份' }}</option>
          <option v-for="item in years" :key="item" :value="item">{{ item }} 年</option>
        </select>
        <ChevronDown :size="16" aria-hidden="true" />
      </span>
    </label>
  </div>
</template>
