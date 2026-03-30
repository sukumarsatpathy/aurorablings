import React, { useState, useEffect } from 'react';
import ImageUploader from '../ImageUploader/ImageUploader';
import ColorPicker from '../../ui/ColorPicker/ColorPicker';
import Toggle from '../../ui/Toggle/Toggle';
import styles from './BannerEditForm.module.css';

/**
 * Props: banner (object), onSave (fn), onCancel (fn), onChange (fn)
 */
const BannerEditForm = ({ banner, onSave, onCancel, onChange }) => {
  const [formData, setFormData] = useState(banner);

  useEffect(() => {
    setFormData(banner);
  }, [banner]);

  const handleChange = (field, value, previewUrl) => {
    const newData = { ...formData, [field]: value };
    if (field === 'imageFile' && previewUrl) {
      newData.image = previewUrl;
    }
    setFormData(newData);
    onChange(newData);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave(formData);
  };

  const POSITION_CHOICES = [
    { value: 'top-left', label: 'Top Left' },
    { value: 'top-right', label: 'Top Right' },
    { value: 'bottom-left', label: 'Bottom Left' },
    { value: 'bottom-right', label: 'Bottom Right' },
    { value: 'dual-banner-left', label: 'Dual Banner Left (Blueberry)' },
    { value: 'dual-banner-right', label: 'Dual Banner Right (Blueberry)' },
  ];

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
            {POSITION_CHOICES.map(choice => (
              <option key={choice.value} value={choice.value}>{choice.label}</option>
            ))}
          </select>
        </div>

        <div className={styles.section}>
          <label className={styles.label}>Title</label>
          <input 
            type="text" 
            value={formData.title} 
            onChange={(e) => handleChange('title', e.target.value)}
            className={styles.input}
            placeholder="e.g. Tasty Snack & Fast food"
          />
        </div>

        <div className={styles.section}>
          <label className={styles.label}>Subtitle (Description)</label>
          <input 
            type="text" 
            value={formData.subtitle || ''} 
            onChange={(e) => handleChange('subtitle', e.target.value)}
            className={styles.input}
            placeholder="e.g. The flavour of something special"
          />
        </div>

        <div className={styles.row}>
          <div className={styles.section}>
            <label className={styles.label}>Badge Bold (e.g. 50%)</label>
            <input 
              type="text" 
              value={formData.badge_bold} 
              onChange={(e) => handleChange('badge_bold', e.target.value)}
              className={styles.input}
            />
          </div>
          <div className={styles.section}>
            <label className={styles.label}>Badge Text</label>
            <input 
              type="text" 
              value={formData.badge_text} 
              onChange={(e) => handleChange('badge_text', e.target.value)}
              className={styles.input}
            />
          </div>
        </div>

        <div className={styles.row}>
          <div className={styles.section}>
            <label className={styles.label}>CTA Label</label>
            <input 
              type="text" 
              value={formData.cta_label} 
              onChange={(e) => handleChange('cta_label', e.target.value)}
              className={styles.input}
            />
          </div>
          <div className={styles.section}>
            <label className={styles.label}>CTA URL</label>
            <input 
              type="text" 
              value={formData.cta_url} 
              onChange={(e) => handleChange('cta_url', e.target.value)}
              className={styles.input}
            />
          </div>
        </div>

        <div className={styles.row}>
          <div className={styles.section}>
            <label className={styles.label}>Background Color</label>
            <ColorPicker 
              value={formData.bg_color} 
              onChange={(val) => handleChange('bg_color', val)} 
            />
          </div>
          <div className={styles.section}>
            <label className={styles.label}>Shape Color (Blueberry Only)</label>
            <ColorPicker 
              value={formData.shape_color} 
              onChange={(val) => handleChange('shape_color', val)} 
            />
          </div>
        </div>

        <div className={styles.section}>
          <label className={styles.label}>Banner Image</label>
          <ImageUploader 
            currentImageUrl={formData.image} 
            onChange={(file, previewUrl) => handleChange('imageFile', file, previewUrl)} 
          />
        </div>

        <div className={styles.section}>
          <Toggle 
            label="Is Active" 
            checked={formData.is_active} 
            onChange={(val) => handleChange('is_active', val)} 
          />
        </div>
      </div>
    </form>
  );
};

export default BannerEditForm;
