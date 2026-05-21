import { computed, onMounted, onUnmounted, ref, watch } from "vue";

type Theme = "light" | "dark" | "system";
type AppliedTheme = "light" | "dark";

const storageKey = "careerpilot.theme";

export function useTheme() {
  const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
  const theme = ref<Theme>(loadTheme());
  const systemTheme = ref<AppliedTheme>(mediaQuery.matches ? "dark" : "light");

  const appliedTheme = computed<AppliedTheme>(() =>
    theme.value === "system" ? systemTheme.value : theme.value,
  );

  function setTheme(nextTheme: Theme) {
    theme.value = nextTheme;
  }

  function toggleTheme() {
    setTheme(appliedTheme.value === "dark" ? "light" : "dark");
  }

  function handleSystemChange(event: MediaQueryListEvent) {
    systemTheme.value = event.matches ? "dark" : "light";
  }

  onMounted(() => {
    applyTheme(appliedTheme.value);
    mediaQuery.addEventListener("change", handleSystemChange);
  });

  onUnmounted(() => {
    mediaQuery.removeEventListener("change", handleSystemChange);
  });

  watch(theme, (nextTheme) => {
    localStorage.setItem(storageKey, nextTheme);
  });

  watch(appliedTheme, applyTheme, { immediate: true });

  return {
    appliedTheme,
    setTheme,
    theme,
    toggleTheme,
  };
}

function applyTheme(theme: AppliedTheme) {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
}

function loadTheme(): Theme {
  const stored = localStorage.getItem(storageKey);
  if (stored === "light" || stored === "dark" || stored === "system") {
    return stored;
  }
  return "system";
}
