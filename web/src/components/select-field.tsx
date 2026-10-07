"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

export type SelectFieldOption<T extends string> = { value: T; label: string };

/**
 * 基于 shadcn Select 的带标签下拉框。
 * 触发按钮带 aria-label，便于无障碍与测试定位（getByRole("combobox", { name })）。
 */
export function SelectField<T extends string>({
  label,
  ariaLabel,
  value,
  onValueChange,
  options,
  disabled,
  placeholder,
  className,
  triggerClassName,
  labelClassName,
}: {
  label?: string;
  ariaLabel?: string;
  value: T | "";
  onValueChange: (value: T) => void;
  options: Array<SelectFieldOption<T>>;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
  triggerClassName?: string;
  labelClassName?: string;
}) {
  const items = Object.fromEntries(
    options.map((option) => [option.value, option.label]),
  );

  return (
    <div className={cn("flex items-center gap-2 text-sm", className)}>
      {label ? <span className={labelClassName}>{label}</span> : null}
      <Select
        value={value === "" ? null : value}
        onValueChange={(next) => onValueChange(next as T)}
        disabled={disabled}
        items={items}
      >
        <SelectTrigger
          aria-label={ariaLabel ?? label}
          className={cn("w-40", triggerClassName)}
        >
          <SelectValue placeholder={placeholder} />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
