import { Input } from '@/components/ui/Input';
import { cn } from '@/lib/utils';

const InputField = ({
  id,
  label,
  value,
  placeholder,
  disabled = false,
  error = '',
  onChange,
}) => {
  return (
    <div className="space-y-2">
      <label htmlFor={id} className="text-sm font-medium text-foreground/90">
        {label}
      </label>
      <Input
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        autoComplete="off"
        spellCheck={false}
        inputMode="text"
        className={cn(
          'bg-white text-slate-900 placeholder:text-slate-400 border-slate-300',
          error ? 'border-destructive/70 focus-visible:border-destructive' : 'focus-visible:border-slate-500'
        )}
      />
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  );
};

export default InputField;
