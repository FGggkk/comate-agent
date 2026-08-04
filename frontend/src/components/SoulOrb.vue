<template>
  <div
    :class="['soul-orb', sizeClass, expression, locked ? 'locked' : '', active ? 'active' : '', hasImage ? 'has-image' : '']"
    :style="orbStyle"
    :aria-label="label"
  >
    <img v-if="hasImage" :src="props.template.avatar_image" class="soul-orb-img" alt="" />
    <template v-else>
      <div class="soul-orb-body">
        <span class="soul-eye left"></span>
        <span class="soul-eye right"></span>
        <span class="soul-cheek left"></span>
        <span class="soul-cheek right"></span>
        <span :class="['soul-mouth', expression]"></span>
        <span v-if="expression === 'firm'" class="soul-brow left"></span>
        <span v-if="expression === 'firm'" class="soul-brow right"></span>
        <span v-if="expression === 'wink'" class="soul-wink right"></span>
        <span v-if="expression === 'mentor'" class="soul-glasses"></span>
      </div>
      <div class="soul-sprout"><span></span></div>
    </template>
    <div v-if="locked" class="soul-lock">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
        <rect x="5" y="11" width="14" height="10" rx="2" />
        <path d="M8 11V8a4 4 0 0 1 8 0v3" />
      </svg>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  template: { type: Object, default: () => ({}) },
  size: { type: String, default: 'md' },
  locked: { type: Boolean, default: false },
  active: { type: Boolean, default: false },
})

const expression = computed(() => props.template?.orb?.expression || 'smile')
const label = computed(() => props.template?.name || '人设小球')
const sizeClass = computed(() => `soul-orb-${props.size}`)
const hasImage = computed(() => !!props.template?.avatar_image)
const orbStyle = computed(() => {
  // 有头像图时无渐变兜底
  if (hasImage.value) return {}
  const colors = props.template?.orb?.colors || ['#FFD8B8', '#FFB088']
  // 自定义角色有 color 时用 color 渐变，保证每个角色样式不同
  const base = props.template?.color
  if (base) return { '--orb-a': base, '--orb-b': base + 'aa' }
  return {
    '--orb-a': colors[0],
    '--orb-b': colors[1],
  }
})
</script>

<style scoped>
.soul-orb {
  --orb-size: 56px;
  --orb-a: #FFD8B8;
  --orb-b: #FFB088;
  position: relative;
  width: var(--orb-size);
  height: var(--orb-size);
  flex: 0 0 auto;
}
.soul-orb-xs { --orb-size: 30px; }
.soul-orb-sm { --orb-size: 42px; }
.soul-orb-md { --orb-size: 58px; }
.soul-orb-lg { --orb-size: 92px; }
.soul-orb.has-image {
  border-radius: 50%;
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(0,0,0,.12);
}
.soul-orb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.soul-orb-body {
  position: absolute;
  inset: 5%;
  border-radius: 48% 52% 46% 54% / 50% 48% 52% 50%;
  background:
    radial-gradient(circle at 34% 28%, rgba(255,255,255,.82) 0%, var(--orb-a) 45%, var(--orb-b) 100%);
  box-shadow:
    0 8px 18px color-mix(in srgb, var(--orb-b) 30%, transparent),
    inset 0 -5px 10px rgba(120,70,40,.14),
    inset 0 5px 9px rgba(255,255,255,.45);
}
.soul-orb.active .soul-orb-body {
  box-shadow:
    0 0 0 4px rgba(255,255,255,.92),
    0 0 0 7px color-mix(in srgb, var(--orb-b) 38%, transparent),
    0 10px 22px color-mix(in srgb, var(--orb-b) 30%, transparent),
    inset 0 -5px 10px rgba(120,70,40,.14),
    inset 0 5px 9px rgba(255,255,255,.45);
}
.soul-orb.locked .soul-orb-body {
  filter: grayscale(.8);
  opacity: .45;
}
.soul-eye {
  position: absolute;
  top: 39%;
  width: 12%;
  height: 15%;
  background: #5A3A22;
  border-radius: 50%;
}
.soul-eye.left { left: 27%; }
.soul-eye.right { right: 27%; }
.soul-eye::after {
  content: "";
  position: absolute;
  top: 12%;
  left: 18%;
  width: 38%;
  height: 38%;
  background: #fff;
  border-radius: 50%;
}
.soul-wink.right {
  position: absolute;
  top: 43%;
  right: 25%;
  width: 15%;
  height: 2px;
  border-radius: 2px;
  background: #5A3A22;
}
.soul-orb.wink .soul-eye.right { display: none; }
.soul-cheek {
  position: absolute;
  top: 55%;
  width: 17%;
  height: 9%;
  background: rgba(255,120,140,.34);
  border-radius: 50%;
  filter: blur(2px);
}
.soul-cheek.left { left: 15%; }
.soul-cheek.right { right: 15%; }
.soul-mouth {
  position: absolute;
  left: 50%;
  top: 58%;
  width: 24%;
  height: 12%;
  transform: translateX(-50%);
  border: 2px solid #5A3A22;
  border-top: none;
  border-radius: 0 0 50% 50%;
}
.soul-mouth.calm {
  width: 22%;
  height: 2px;
  top: 62%;
  border: none;
  border-radius: 2px;
  background: #5A3A22;
}
.soul-mouth.firm {
  width: 24%;
  height: 2px;
  top: 63%;
  border: none;
  border-radius: 2px;
  background: #5A3A22;
}
.soul-mouth.mentor {
  width: 19%;
}
.soul-brow {
  position: absolute;
  top: 31%;
  width: 15%;
  height: 2px;
  border-radius: 2px;
  background: #5A3A22;
}
.soul-brow.left {
  left: 24%;
  transform: rotate(18deg);
}
.soul-brow.right {
  right: 24%;
  transform: rotate(-18deg);
}
.soul-glasses {
  position: absolute;
  left: 24%;
  top: 36%;
  width: 52%;
  height: 18%;
  border-left: 2px solid rgba(90,58,34,.5);
  border-right: 2px solid rgba(90,58,34,.5);
}
.soul-glasses::before,
.soul-glasses::after {
  content: "";
  position: absolute;
  top: 0;
  width: 35%;
  height: 100%;
  border: 2px solid rgba(90,58,34,.45);
  border-radius: 50%;
}
.soul-glasses::before { left: 0; }
.soul-glasses::after { right: 0; }
.soul-sprout {
  position: absolute;
  top: -10%;
  left: 50%;
  width: 40%;
  height: 28%;
  transform: translateX(-50%);
}
.soul-sprout::before {
  content: "";
  position: absolute;
  bottom: 2px;
  left: 50%;
  width: 4px;
  height: 100%;
  transform: translateX(-50%);
  border-radius: 2px;
  background: linear-gradient(to top, var(--sprout), var(--sprout-2));
}
.soul-sprout::after,
.soul-sprout span {
  content: "";
  position: absolute;
  bottom: 32%;
  width: 50%;
  height: 55%;
  background: linear-gradient(135deg, #A8E6CF, #5FBE63);
  box-shadow: 0 2px 6px rgba(94,170,120,.15);
}
.soul-sprout::after {
  left: 2%;
  border-radius: 60% 10% 60% 20%;
  transform: rotate(-30deg);
  transform-origin: right bottom;
}
.soul-sprout span {
  right: 2%;
  border-radius: 10% 60% 20% 60%;
  transform: rotate(30deg);
  transform-origin: left bottom;
}
.soul-lock {
  position: absolute;
  right: -2px;
  bottom: -2px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: rgba(255,255,255,.92);
  border: 1px solid var(--line);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--sub);
  box-shadow: var(--shadow-sm);
}
.soul-lock svg {
  width: 13px;
  height: 13px;
  stroke-width: 2.4;
}
</style>
