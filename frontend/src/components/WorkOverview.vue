<script setup lang="ts">
import { computed } from 'vue'
import { assetPath } from '../works'
import type { Work } from '../works'

const props = defineProps<{ work: Work }>()
const photos = computed(() => props.work.assets.filter(item => item.kind === 'photo'))
</script>

<template>
  <div v-if="work.team_name || work.team_members || work.team_intro || photos.length || work.award_info || work.ip_details" class="work-overview">
    <div v-if="work.team_name || work.team_members || work.team_intro || photos.length" class="work-team-layout">
      <section v-if="work.team_name || work.team_members || work.team_intro" class="work-detail-panel">
        <h2>团队介绍</h2>
        <dl v-if="work.team_name || work.team_members" class="work-detail-facts">
          <div v-if="work.team_name"><dt>团队名称</dt><dd>{{ work.team_name }}</dd></div>
          <div v-if="work.team_members"><dt>团队成员</dt><dd>{{ work.team_members }}</dd></div>
        </dl>
        <p v-if="work.team_intro" class="work-detail-prose">{{ work.team_intro }}</p>
      </section>
      <section v-if="photos.length" class="work-detail-panel">
        <h2>团队风采</h2>
        <ul class="team-photos">
          <li v-for="(photo, index) in photos" :key="photo.id">
            <img :src="assetPath(work, photo, 'photo')" :alt="'比赛照片 ' + (index + 1) + ' · ' + photo.original_name"
              loading="lazy" decoding="async">
          </li>
        </ul>
      </section>
    </div>
    <section v-if="work.award_info || work.ip_details" class="work-detail-panel work-results">
      <h2>获奖与成果</h2>
      <dl class="work-detail-facts">
        <div v-if="work.award_info"><dt>获奖情况</dt><dd>{{ work.award_info }}</dd></div>
        <div v-if="work.ip_details"><dt>论文、专利与软著</dt><dd>{{ work.ip_details }}</dd></div>
      </dl>
    </section>
  </div>
</template>
