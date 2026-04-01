import React, { useEffect, useMemo, useRef, useState } from 'react';
import ColorPicker from '../../ui/ColorPicker/ColorPicker';
import Toggle from '../../ui/Toggle/Toggle';
import styles from './BannerEditForm.module.css';

const POSITION_CHOICES = [
  { value: 'top-left', label: 'Top Left' },
  { value: 'top-right', label: 'Top Right' },
  { value: 'bottom-left', label: 'Bottom Left' },
  { value: 'bottom-right', label: 'Bottom Right' },
  { value: 'dual-banner-left', label: 'Dual Banner Left (Blueberry)' },
  { value: 'dual-banner-right', label: 'Dual Banner Right (Blueberry)' },
];

const LAYERS = [
  { key: 'badge_bold', label: 'Badge Bold', xKey: 'badge_bold_x', yKey: 'badge_bold_y' },
  { key: 'badge_text', label: 'Badge Text', xKey: 'badge_text_x', yKey: 'badge_text_y' },
  { key: 'title', label: 'Title', xKey: 'title_x', yKey: 'title_y' },
  { key: 'subtitle', label: 'Subtitle', xKey: 'subtitle_x', yKey: 'subtitle_y' },
  { key: 'cta_label', label: 'Shop Button', xKey: 'cta_x', yKey: 'cta_y' },
];

const DEFAULT_POSITIONS = {
  title_x: 8,
  title_y: 46,
  subtitle_x: 8,
  subtitle_y: 64,
  cta_x: 8,
  cta_y: 80,
  badge_bold_x: 8,
  badge_bold_y: 22,
  badge_text_x: 22,
  badge_text_y: 22,
};

const clampPercent = (value) => Math.max(0, Math.min(100, Number(value) || 0));

const withDefaults = (banner) => ({
  subtitle: '',
  badge_bold: '',
  badge_text: '',
  cta_label: 'SHOP NOW',
  cta_url: '#',
  bg_color: '#F5F0EB',
  shape_color: '#F4DBB5',
  title_color: '#1A1A1A',
  subtitle_color: '#1A1A1A',
  badge_color: '#1A1A1A',
  cta_text_color: '#1A1A1A',
  cta_border_color: '#1A1A1A',
  ...DEFAULT_POSITIONS,
  ...banner,
});

const BannerEditForm = ({ banner, onSave, onCancel, onChange }) => {
  const [formData, setFormData] = useState(withDefaults(banner));
  const [dragLayer, setDragLayer] = useState(null);
  const canvasRef = useRef(null);

  useEffect(() => {
    setFormData(withDefaults(banner));
  }, [banner]);

  useEffect(() => {
    if (!dragLayer) return undefined;

    const onMouseMove = (event) => {
      if (!canvasRef.current) return;
      const rect = canvasRef.current.getBoundingClientRect();
      const dx = ((event.clientX - dragLayer.startClientX) / rect.width) * 100;
      const dy = ((event.clientY - dragLayer.startClientY) / rect.height) * 100;
      const nextX = clampPercent(dragLayer.startX + dx);
      const nextY = clampPercent(dragLayer.startY + dy);

      setFormData((prev) => {
        const updated = {
          ...prev,
          [dragLayer.xKey]: Math.round(nextX),
          [dragLayer.yKey]: Math.round(nextY),
        };
        onChange(updated);
        return updated;
      });
    };

    const onMouseUp = () => setDragLayer(null);

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
  }, [dragLayer, onChange]);

  const handleChange = (field, value) => {
    const updated = { ...formData, [field]: value };
    setFormData(updated);
    onChange(updated);
  };

  const handleCoordinateChange = (key, value) => {
    handleChange(key, clampPercent(value));
  };

  const handleDragStart = (event, layer) => {
    event.preventDefault();
    setDragLayer({
      xKey: layer.xKey,
      yKey: layer.yKey,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startX: clampPercent(formData[layer.xKey]),
      startY: clampPercent(formData[layer.yKey]),
    });
  };

  const handleResetLayout = () => {
    const updated = { ...formData, ...DEFAULT_POSITIONS };
    setFormData(updated);
    onChange(updated);
  };

  const canvasStyle = useMemo(() => ({
    backgroundColor: formData.bg_color || '#F5F0EB',
    backgroundImage: formData.image ? `url(${formData.image})` : 'none',
  }), [formData.bg_color, formData.image]);

  const renderLayerText = (key) => {
    if (key === 'badge_bold') return formData.badge_bold || '50%';
    if (key === 'badge_text') return formData.badge_text || 'off select items';
    if (key === 'title') return formData.title || 'Banner Title';
    if (key === 'subtitle') return formData.subtitle || 'Banner subtitle';
    if (key === 'cta_label') return (formData.cta_label || 'Shop Now').toUpperCase();
    return '';
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave(formData);
  };

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <div className={styles.header}>
        <h2 className={styles.title}>
          {banner.id ? `Edit Banner: ${banner.position}` : 'Create New Banner'}
        </h2>
        <div className={styles.actions}>
          <button type="button" onClick={onCancel} className={styles.cancelBtn}>Cancel</button>
          <button type="submit" className={styles.saveBtn}>
            {banner.id ? 'Save Changes' : 'Create Banner'}
          </button>
        </div>
      </div>

      <div className={styles.grid}>
        <div className={styles.section}>
          <label className={styles.label}>Grid Position</label>
          <select
            value={formData.position}
            onChange={(e) => handleChange('position', e.target.value)}
            className={styles.input}
          >
            {POSITION_CHOICES.map((choice) => (
              <option key={choice.value} value={choice.value}>{choice.label}</option>
            ))}
          </select>
        </div>

        <div className={styles.row}>
          <div className={styles.section}>
            <label className={styles.label}>Title (Optional)</label>
            <input
              type="text"
              value={formData.title || ''}
              onChange={(e) => handleChange('title', e.target.value)}
              className={styles.input}
              placeholder="Leave empty to hide title"
            />
          </div>
          <div className={styles.section}>
            <label className={styles.label}>Subtitle (Optional)</label>
            <input
              type="text"
              value={formData.subtitle || ''}
              onChange={(e) => handleChange('subtitle', e.target.value)}
              className={styles.input}
              placeholder="Leave empty to hide subtitle"
            />
          </div>
        </div>

        <div className={styles.row}>
          <div className={styles.section}>
            <label className={styles.label}>Badge Bold</label>
            <input
              type="text"
              value={formData.badge_bold || ''}
              onChange={(e) => handleChange('badge_bold', e.target.value)}
              className={styles.input}
              placeholder="e.g. 50%"
            />
          </div>
          <div className={styles.section}>
            <label className={styles.label}>Badge Text</label>
            <input
              type="text"
              value={formData.badge_text || ''}
              onChange={(e) => handleChange('badge_text', e.target.value)}
              className={styles.input}
              placeholder="e.g. off select items"
            />
          </div>
        </div>

        <div className={styles.row}>
          <div className={styles.section}>
            <label className={styles.label}>CTA Label</label>
            <input
              type="text"
              value={formData.cta_label || ''}
              onChange={(e) => handleChange('cta_label', e.target.value)}
              className={styles.input}
            />
          </div>
          <div className={styles.section}>
            <label className={styles.label}>CTA URL</label>
            <input
              type="text"
              value={formData.cta_url || ''}
              onChange={(e) => handleChange('cta_url', e.target.value)}
              className={styles.input}
            />
          </div>
        </div>

        <div className={styles.row}>
          <div className={styles.section}>
            <label className={styles.label}>Background Color</label>
            <ColorPicker value={formData.bg_color} onChange={(val) => handleChange('bg_color', val)} />
          </div>
          <div className={styles.section}>
            <label className={styles.label}>Shape Color (Blueberry Only)</label>
            <ColorPicker value={formData.shape_color} onChange={(val) => handleChange('shape_color', val)} />
          </div>
        </div>

        <div className={styles.row}>
          <div className={styles.section}>
            <label className={styles.label}>Title Color</label>
            <ColorPicker value={formData.title_color} onChange={(val) => handleChange('title_color', val)} />
          </div>
          <div className={styles.section}>
            <label className={styles.label}>Subtitle Color</label>
            <ColorPicker value={formData.subtitle_color} onChange={(val) => handleChange('subtitle_color', val)} />
          </div>
        </div>

        <div className={styles.row}>
          <div className={styles.section}>
            <label className={styles.label}>Badge Color</label>
            <ColorPicker value={formData.badge_color} onChange={(val) => handleChange('badge_color', val)} />
          </div>
          <div className={styles.section}>
            <label className={styles.label}>Button Text/Border Color</label>
            <ColorPicker
              value={formData.cta_text_color}
              onChange={(val) => {
                handleChange('cta_text_color', val);
                handleChange('cta_border_color', val);
              }}
            />
          </div>
        </div>

        <div className={styles.section}>
          <div className={styles.editorHead}>
            <label className={styles.label}>Drag Layout Editor</label>
            <button type="button" className={styles.linkBtn} onClick={handleResetLayout}>Reset Layout</button>
          </div>
          <div className={styles.editorHint}>
            Drag each layer directly on preview. You can also set exact X/Y (%) below.
          </div>
          <div ref={canvasRef} className={styles.layoutCanvas} style={canvasStyle}>
            <div className={styles.canvasOverlay} />
            {LAYERS.map((layer) => (
              <div
                key={layer.key}
                className={`${styles.layer} ${layer.key === 'cta_label' ? styles.layerButton : ''}`}
                style={{
                  left: `${clampPercent(formData[layer.xKey])}%`,
                  top: `${clampPercent(formData[layer.yKey])}%`,
                  color: layer.key.startsWith('badge') ? formData.badge_color : (layer.key === 'subtitle' ? formData.subtitle_color : formData.title_color),
                  borderColor: layer.key === 'cta_label' ? formData.cta_border_color : 'transparent',
                }}
                onMouseDown={(e) => handleDragStart(e, layer)}
              >
                {renderLayerText(layer.key)}
              </div>
            ))}
          </div>
        </div>

        <div className={styles.coordGrid}>
          {LAYERS.map((layer) => (
            <div key={`coord-${layer.key}`} className={styles.coordCard}>
              <div className={styles.coordTitle}>{layer.label}</div>
              <div className={styles.coordRow}>
                <label className={styles.coordLabel}>X%</label>
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={clampPercent(formData[layer.xKey])}
                  onChange={(e) => handleCoordinateChange(layer.xKey, e.target.value)}
                  className={styles.input}
                />
              </div>
              <div className={styles.coordRow}>
                <label className={styles.coordLabel}>Y%</label>
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={clampPercent(formData[layer.yKey])}
                  onChange={(e) => handleCoordinateChange(layer.yKey, e.target.value)}
                  className={styles.input}
                />
              </div>
            </div>
          ))}
        </div>

        <div className={styles.section}>
          <Toggle
            label="Is Active"
            checked={!!formData.is_active}
            onChange={(val) => handleChange('is_active', val)}
          />
        </div>
      </div>
    </form>
  );
};

export default BannerEditForm;
