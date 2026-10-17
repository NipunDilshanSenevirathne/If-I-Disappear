import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "../../state/app";
import type { ThemeChoice } from "../../lib/theme";

const OPTIONS: { value: ThemeChoice; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "Same as this device", icon: Monitor },
];

export function ThemeToggle({ withLabels = false }: { withLabels?: boolean }) {
  const { choice, setChoice } = useTheme();
  return (
    <div className={`theme-toggle ${withLabels ? "labelled" : ""}`} role="radiogroup" aria-label="Colour theme">
      {OPTIONS.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={choice === o.value}
          className={choice === o.value ? "on" : ""}
          title={o.label}
          aria-label={o.label}
          onClick={() => setChoice(o.value)}
        >
          <o.icon size={15} aria-hidden="true" />
          {withLabels && <span>{o.value === "system" ? "Auto" : o.label}</span>}
        </button>
      ))}
    </div>
  );
}
