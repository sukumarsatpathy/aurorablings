import React, { useState, useEffect } from 'react';
import BannerList from '../../../components/admin/BannerList/BannerList';
import BannerEditForm from '../../../components/admin/BannerEditForm/BannerEditForm';
import BannerPreview from '../../../components/admin/BannerPreview/BannerPreview';
import { bannersApi } from '../../../api/bannersApi';
import styles from './AdminBannersPage.module.css';

const AdminBannersPage = () => {
  const [banners, setBanners] = useState([]);
  const [selectedBanner, setSelectedBanner] = useState(null);
  const [previewBanners, setPreviewBanners] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchBanners();
  }, []);

  const fetchBanners = async () => {
    try {
      setLoading(true);
      const data = await bannersApi.getAll();
      // Aurora Blings standard envelope uses 'data' key
      const bannerList = data.data || data.results || (Array.isArray(data) ? data : []);
      setBanners(bannerList);
      setPreviewBanners(bannerList);
    } catch (err) {
      console.error('Failed to fetch banners:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleReorder = async (newBanners) => {
    setBanners(newBanners);
    setPreviewBanners(newBanners);
    try {
      const orderData = newBanners.map((b, idx) => ({ id: b.id, order: idx }));
      await bannersApi.reorder(orderData);
      setError('');
    } catch (err) {
      console.error('Failed to save order:', err);
      setError('Failed to save banner order. Please try again.');
    }
  };

  const handleToggle = async (id, isActive) => {
    try {
      const updated = banners.map(b => b.id === id ? { ...b, is_active: isActive } : b);
      setBanners(updated);
      setPreviewBanners(updated);
      const payload = new FormData();
      payload.append('is_active', String(isActive));
      await bannersApi.update(id, payload);
      setError('');
    } catch (err) {
      console.error('Failed to toggle banner:', err);
      setError('Failed to update banner status.');
    }
  };

  const handleNewClick = () => {
    const POSITION_CHOICES = [
      'top-left', 'top-right', 'bottom-left', 'bottom-right',
      'dual-banner-left', 'dual-banner-right'
    ];
    const usedPositions = new Set(banners.map(b => b.position));
    const availablePosition = POSITION_CHOICES.find(pos => !usedPositions.has(pos));
    if (!availablePosition) {
      setError('All banner positions are already in use. Edit an existing banner instead.');
      return;
    }

    const newBanner = {
      id: 'temp-' + Date.now(), // Temporary ID for preview mapping
      title: '',
      badge_bold: '',
      badge_text: '',
      cta_label: 'SHOP NOW',
      cta_url: '#',
      bg_color: '#f5f0eb',
      position: availablePosition,
      is_active: true,
      image: null
    };
    setSelectedBanner(newBanner);
    setPreviewBanners([...banners, newBanner]);
    setError('');
  };

  const handleSave = async (formData) => {
    try {
      setSaving(true);
      const trimmedTitle = (formData.title || '').trim();
      const trimmedUrl = (formData.cta_url || '').trim();
      if (!formData.position) {
        setError('Please select a grid position for this banner.');
        return;
      }
      if (!trimmedTitle) {
        setError('Banner title is required.');
        return;
      }
      if (!trimmedUrl) {
        setError('CTA URL is required.');
        return;
      }

      const isNew = String(formData.id).startsWith('temp-');
      const positionTaken = banners.some(
        (b) => b.position === formData.position && (isNew || b.id !== formData.id)
      );
      if (positionTaken) {
        setError('That grid position is already used. Please choose another.');
        return;
      }

      const data = new FormData();
      Object.keys(formData).forEach(key => {
        if (key === 'imageFile' && formData[key]) {
          data.append('image', formData[key]);
        } else if (
          key !== 'image' &&
          key !== 'imageFile' &&
          key !== 'id' &&
          formData[key] !== null &&
          formData[key] !== undefined
        ) {
          data.append(key, formData[key]);
        }
      });

      if (!isNew) {
        await bannersApi.update(formData.id, data);
      } else {
        await bannersApi.create(data);
      }
      fetchBanners();
      setSelectedBanner(null);
      setError('');
    } catch (err) {
      console.error('Failed to save banner:', err);
      const apiMessage = err?.response?.data?.message;
      setError(apiMessage || 'Failed to save banner. Please check the inputs.');
    } finally {
      setSaving(false);
    }
  };

  const handleFormChange = (updatedBanner) => {
    setPreviewBanners(prev => prev.map(b => b.id === updatedBanner.id ? updatedBanner : b));
  };

  if (loading) return <div className="p-8">Loading banners...</div>;

  return (
    <div className={styles.page}>
      <div className={styles.left}>
        <div className="flex justify-between items-center mb-4">
             <h2 className="text-xl font-bold">Promo Banners</h2>
             <button onClick={handleNewClick} className="bg-primary text-white px-4 py-2 rounded-lg text-sm font-medium">+ New Banner</button>
        </div>
        {error ? (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : null}
        <BannerList 
          banners={banners} 
          onReorder={handleReorder}
          onSelect={setSelectedBanner}
          onToggle={handleToggle}
        />
      </div>
      
      <div className={styles.right}>
        {selectedBanner ? (
          <>
            <BannerEditForm 
              banner={selectedBanner} 
              onSave={handleSave}
              onCancel={() => {
                setSelectedBanner(null);
                setPreviewBanners(banners);
                setError('');
              }}
              onChange={handleFormChange}
            />
            {saving ? (
              <div className="mt-3 text-xs text-muted-foreground">Saving banner...</div>
            ) : null}
            <div className="mt-8">
              <BannerPreview banners={previewBanners} />
            </div>
          </>
        ) : (
          <div className={styles.emptyState}>
            <p>Select a banner from the list to edit its content.</p>
            <div className="mt-8 scale-75 origin-top">
                <BannerPreview banners={banners} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AdminBannersPage;
