<script setup lang="ts">
import { computed, nextTick, ref, useId } from 'vue'
import { Check, ChevronDown, Search } from '@lucide/vue'
import type { FilterValue } from '../works'

const props = defineProps<{
  label: string
  options: { value: FilterValue; label: string }[]
  searchable?: boolean
  disabled?: boolean
}>()
const value = defineModel<FilterValue>({ required: true })
const panelId = useId()
const open = ref(false)
const query = ref('')
const root = ref<HTMLElement>()
const trigger = ref<HTMLButtonElement>()
const search = ref<HTMLInputElement>()
const selectedLabel = computed(() => props.options.find(option => option.value === value.value)?.label ?? props.label)
const options = computed(() => {
  const term = query.value.trim().toLocaleLowerCase()
  return term ? props.options.filter(option => option.label.toLocaleLowerCase().includes(term)) : props.options
})

function buttons() {
  return Array.from(root.value?.querySelectorAll<HTMLButtonElement>('.glass-filter-option') ?? [])
}

async function toggle() {
  open.value = !open.value
  if (!open.value) return
  query.value = ''
  await nextTick()
  if (search.value) search.value.focus()
  else (buttons().find(option => option.getAttribute('aria-pressed') === 'true') ?? buttons()[0])?.focus()
}

function dismiss() {
  if (!open.value) return
  open.value = false
  trigger.value?.focus()
}

function onFocusOut(event: FocusEvent) {
  if (!root.value?.contains(event.relatedTarget as Node | null)) open.value = false
}

function move(event: KeyboardEvent, direction: number) {
  if (!open.value) return
  event.preventDefault()
  const items = buttons()
  const index = items.findIndex(option => option === event.target)
  items[index < 0 ? direction > 0 ? 0 : items.length - 1 : (index + direction + items.length) % items.length]?.focus()
}
</script>

<template>
  <div ref="root" class="glass-filter" @focusout="onFocusOut" @keydown.esc.stop="dismiss"
    @keydown.down="move($event, 1)" @keydown.up="move($event, -1)">
    <button ref="trigger" class="glass-button glass-filter-trigger" type="button" :disabled="disabled"
      :aria-label="label + '：' + selectedLabel" :aria-expanded="open" :aria-controls="open ? panelId : undefined" :title="selectedLabel" @click="toggle">
      <slot name="icon" />
      <span>{{ selectedLabel }}</span>
      <ChevronDown class="glass-filter-chevron" :size="16" aria-hidden="true" />
    </button>
    <div v-if="open && !disabled" :id="panelId" class="glass-filter-panel glass-panel" role="group" :aria-label="label">
      <label v-if="searchable" class="glass-filter-search">
        <Search :size="16" aria-hidden="true" />
        <input ref="search" v-model="query" type="search" aria-label="查找比赛" placeholder="查找比赛">
      </label>
      <ul v-if="options.length" class="glass-filter-options">
        <li v-for="option in options" :key="option.value">
          <button class="glass-filter-option" type="button" :aria-pressed="value === option.value" @click="value = option.value; dismiss()">
            <span>{{ option.label }}</span>
            <Check v-if="value === option.value" :size="16" aria-hidden="true" />
          </button>
        </li>
      </ul>
      <p v-else class="glass-filter-empty">没有匹配的比赛。</p>
    </div>
  </div>
</template>
