import { cn } from "@/lib/utils";

type LogoMarkProps = {
  className?: string;
};

type LogoWordmarkProps = {
  className?: string;
  nameClassName?: string;
  descriptorClassName?: string;
  descriptor?: string;
  showDescriptor?: boolean;
  size?: "sm" | "md" | "lg";
};

type LogoLockupProps = LogoWordmarkProps & {
  markClassName?: string;
};

const SIZE_STYLES = {
  sm: {
    mark: "h-9 w-9",
    name: "text-lg",
    descriptor: "text-[0.62rem]",
    gap: "gap-2.5",
  },
  md: {
    mark: "h-10 w-10",
    name: "text-xl",
    descriptor: "text-[0.66rem]",
    gap: "gap-3",
  },
  lg: {
    mark: "h-14 w-14",
    name: "text-3xl",
    descriptor: "text-[0.72rem]",
    gap: "gap-3.5",
  },
} as const;

export function LogoMark({ className }: LogoMarkProps) {
  return (
    <svg
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn("block", className)}
      aria-hidden="true"
    >
      <rect
        x="4"
        y="4"
        width="40"
        height="40"
        rx="13"
        fill="hsl(var(--surface-panel))"
        stroke="hsl(var(--brand) / 0.18)"
        strokeWidth="1.4"
      />
      <circle
        cx="22"
        cy="22"
        r="10"
        stroke="hsl(var(--brand))"
        strokeWidth="2.4"
      />
      <path
        d="M28.5 28.5L35 35"
        stroke="hsl(var(--accent))"
        strokeWidth="2.6"
        strokeLinecap="round"
      />
      <rect
        x="15"
        y="24"
        width="3.5"
        height="6.5"
        rx="1.75"
        fill="hsl(var(--brand) / 0.55)"
      />
      <rect
        x="21"
        y="20.5"
        width="3.5"
        height="10"
        rx="1.75"
        fill="hsl(var(--brand) / 0.78)"
      />
      <rect
        x="27"
        y="17"
        width="3.5"
        height="13.5"
        rx="1.75"
        fill="hsl(var(--accent) / 0.78)"
      />
      <path
        d="M12.5 29.5C16.1 27.6 19.6 24.8 23.1 21.2C25.5 18.7 28.1 16.9 31 15.8"
        stroke="hsl(var(--foreground) / 0.18)"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function LogoWordmark({
  className,
  nameClassName,
  descriptorClassName,
  descriptor = "Decision engine",
  showDescriptor = true,
  size = "md",
}: LogoWordmarkProps) {
  const styles = SIZE_STYLES[size];

  return (
    <div className={cn("min-w-0 leading-none", className)}>
      <div
        className={cn(
          "font-serif font-semibold tracking-[-0.06em] text-foreground",
          styles.name,
          nameClassName
        )}
      >
        Opti<span className="text-primary">q</span>al
      </div>
      {showDescriptor ? (
        <div
          className={cn(
            "mt-1 font-mono uppercase tracking-[0.24em] text-muted-foreground",
            styles.descriptor,
            descriptorClassName
          )}
        >
          {descriptor}
        </div>
      ) : null}
    </div>
  );
}

export function LogoLockup({
  className,
  markClassName,
  size = "md",
  ...wordmarkProps
}: LogoLockupProps) {
  const styles = SIZE_STYLES[size];

  return (
    <div className={cn("flex items-center", styles.gap, className)}>
      <LogoMark className={cn(styles.mark, markClassName)} />
      <LogoWordmark size={size} {...wordmarkProps} />
    </div>
  );
}
