import React, { useState, useEffect } from 'react';
import styles from './ImageUploader.module.css';

const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024;

/**
 * Props: currentImageUrl (string|null), onChange(file: File) (fn)
 */
const ImageUploader = ({ currentImageUrl, onChange }) => {
  const [preview, setPreview] = useState(currentImageUrl);
  const [objectUrl, setObjectUrl] = useState(null);

  useEffect(() => {
    setPreview(currentImageUrl);
  }, [currentImageUrl]);

  useEffect(() => {
    return () => {
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [objectUrl]);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
        alert('Only JPG, PNG, and WEBP images are allowed.');
        e.target.value = '';
        return;
      }
      if (file.size > MAX_IMAGE_SIZE_BYTES) {
        alert('Image must be 5 MB or smaller.');
        e.target.value = '';
        return;
      }
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
      const nextUrl = URL.createObjectURL(file);
      setObjectUrl(nextUrl);
      setPreview(nextUrl);
      onChange(file, nextUrl);
    }
  };

  return (
    <div className={styles.uploader}>
      <div className={styles.preview}>
        {preview ? (
          <img src={preview} alt="Preview" className={styles.image} />
        ) : (
          <div className={styles.placeholder}>No image selected</div>
        )}
      </div>
      <label className={styles.button}>
        Change Image
        <input type="file" accept="image/jpeg,image/png,image/webp" onChange={handleFileChange} />
      </label>
    </div>
  );
};

export default ImageUploader;
