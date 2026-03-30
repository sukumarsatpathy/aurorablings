import React from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical } from 'lucide-react';
import Toggle from '../../ui/Toggle/Toggle';
import styles from './BannerList.module.css';

const BannerListRow = ({ banner, onClick, onToggle }) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
  } = useSortable({ id: banner.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div 
      ref={setNodeRef} 
      style={style} 
      className={styles.row}
      onClick={onClick}
    >
      <div className={styles.dragHandle} {...attributes} {...listeners}>
        <GripVertical size={20} />
      </div>
      
      <div className={styles.thumbnail}>
        {banner.image ? (
          <img src={banner.image} alt="" />
        ) : (
          <div style={{ backgroundColor: banner.bg_color }} className={styles.colorThumb} />
        )}
      </div>

      <div className={styles.info}>
        <span className={styles.position}>{banner.position}</span>
        <span className={styles.bannerTitle}>{banner.title}</span>
      </div>

      <div className={styles.actions} onClick={(e) => e.stopPropagation()}>
        <Toggle 
          checked={banner.is_active} 
          onChange={onToggle} 
        />
      </div>
    </div>
  );
};

export default BannerListRow;
