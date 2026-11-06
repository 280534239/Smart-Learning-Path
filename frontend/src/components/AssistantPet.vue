<script setup>
defineProps({
  variant: {
    type: String,
    default: 'full',
  },
})
</script>

<template>
  <svg
    class="pet-illustration"
    :class="variant"
    viewBox="0 0 120 120"
    role="img"
    aria-label="智学桌面宠物"
  >
    <ellipse
      class="pet-shadow"
      cx="60"
      cy="108"
      rx="31"
      ry="6"
    />

    <g class="pet-character">
      <path
        class="pet-tail"
        d="M88 84c18-9 23-26 11-39"
      />

      <path
        class="pet-arm pet-arm-left"
        d="M35 76c-10 2-16 9-14 15"
      />
      <path
        class="pet-arm pet-arm-right"
        d="M84 76c10 2 16 9 14 15"
      />

      <g class="pet-sprout">
        <path d="M60 35c0-12-3-18-12-22" />
        <path
          class="pet-leaf"
          d="M49 15c-8-5-13-1-13 5 4 4 9 4 13-5Z"
        />
        <circle cx="60" cy="11" r="4" />
      </g>

      <path
        class="pet-body"
        d="M31 55c0-18 12-28 29-28s29 10 29 28l-3 35c-1 10-8 15-17 15H51c-9 0-16-5-17-15l-3-35Z"
      />
      <path
        class="pet-ear pet-ear-left"
        d="M35 43 25 27c-2-4 2-7 6-5l16 10"
      />
      <path
        class="pet-ear pet-ear-right"
        d="m85 43 10-16c2-4-2-7-6-5L73 32"
      />

      <rect
        class="pet-face"
        x="37"
        y="43"
        width="46"
        height="40"
        rx="19"
      />

      <g class="pet-eyes">
        <circle cx="49" cy="62" r="3.5" />
        <circle cx="71" cy="62" r="3.5" />
        <circle class="pet-eye-light" cx="50" cy="61" r="1.1" />
        <circle class="pet-eye-light" cx="72" cy="61" r="1.1" />
      </g>
      <ellipse class="pet-cheek" cx="43" cy="71" rx="4" ry="2" />
      <ellipse class="pet-cheek" cx="77" cy="71" rx="4" ry="2" />
      <path class="pet-smile" d="M56 70c2 3 7 3 9 0" />

      <path
        class="pet-scarf"
        d="M39 83c12 6 31 6 42 0l-2 10c-11 4-27 4-38 0l-2-10Z"
      />
      <circle class="pet-badge" cx="60" cy="96" r="7" />
      <path class="pet-badge-mark" d="M57 96h6M60 93v6" />

      <path class="pet-foot" d="M42 104c0 4 3 6 8 6h2v-6" />
      <path class="pet-foot" d="M78 104c0 4-3 6-8 6h-2v-6" />
    </g>
  </svg>
</template>

<style scoped>
.pet-illustration {
  display: block;
  width: 100%;
  height: 100%;
  overflow: visible;
}

.pet-shadow {
  fill: rgba(15, 44, 62, 0.16);
  transform-origin: 60px 108px;
  animation: pet-shadow-breathe 3.2s ease-in-out infinite;
}

.pet-character {
  transform-origin: 60px 78px;
  animation: pet-float 3.2s ease-in-out infinite;
}

.pet-body,
.pet-ear {
  fill: #dff4ff;
  stroke: #173449;
  stroke-linejoin: round;
  stroke-width: 3;
}

.pet-ear {
  z-index: -1;
}

.pet-face {
  fill: #fffdf5;
  stroke: #173449;
  stroke-width: 2;
}

.pet-tail,
.pet-arm,
.pet-sprout path {
  fill: none;
  stroke: #4ba88e;
  stroke-linecap: round;
}

.pet-tail {
  stroke-width: 7;
}

.pet-arm {
  stroke-width: 8;
}

.pet-arm-left {
  stroke: #5b9fd1;
}

.pet-arm-right {
  stroke: #5b9fd1;
}

.pet-sprout {
  transform-origin: 60px 34px;
  animation: pet-sprout-sway 2.8s ease-in-out infinite;
}

.pet-sprout path {
  stroke-width: 4;
}

.pet-sprout .pet-leaf {
  fill: #8bd9a8;
  stroke-width: 2;
}

.pet-sprout circle {
  fill: #ffd36b;
  stroke: #173449;
  stroke-width: 2;
}

.pet-eyes {
  fill: #173449;
  transform-origin: 60px 62px;
  animation: pet-blink 5.4s ease-in-out infinite;
}

.pet-eye-light {
  fill: #fff;
  animation: none;
}

.pet-cheek {
  fill: #f5a7a7;
  opacity: 0.75;
}

.pet-smile {
  fill: none;
  stroke: #173449;
  stroke-linecap: round;
  stroke-width: 2;
}

.pet-scarf {
  fill: #246BFE;
  stroke: #173449;
  stroke-linejoin: round;
  stroke-width: 2;
}

.pet-badge {
  fill: #ffd36b;
  stroke: #173449;
  stroke-width: 2;
}

.pet-badge-mark {
  fill: none;
  stroke: #173449;
  stroke-linecap: round;
  stroke-width: 2;
}

.pet-foot {
  fill: none;
  stroke: #173449;
  stroke-linecap: round;
  stroke-width: 4;
}

.mini .pet-shadow,
.mini .pet-tail,
.mini .pet-arm,
.mini .pet-foot {
  display: none;
}

.mini .pet-character,
.mini .pet-sprout,
.mini .pet-eyes,
.mini .pet-shadow {
  animation: none;
}

@keyframes pet-float {
  0%,
  100% {
    transform: translateY(0) rotate(-1deg);
  }

  50% {
    transform: translateY(-5px) rotate(1deg);
  }
}

@keyframes pet-shadow-breathe {
  0%,
  100% {
    opacity: 0.8;
    transform: scaleX(1);
  }

  50% {
    opacity: 0.5;
    transform: scaleX(0.82);
  }
}

@keyframes pet-blink {
  0%,
  44%,
  50%,
  100% {
    transform: scaleY(1);
  }

  47% {
    transform: scaleY(0.08);
  }
}

@keyframes pet-sprout-sway {
  0%,
  100% {
    transform: rotate(-4deg);
  }

  50% {
    transform: rotate(5deg);
  }
}
</style>
