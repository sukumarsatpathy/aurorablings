import React from 'react';
import {
  DndContext, 
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import BannerListRow from './BannerListRow';
import styles from './BannerList.module.css';

/**
 * Props: banners (array), onReorder (fn), onSelect (fn), onToggle (fn)
 */
const BannerList = ({ banners, onReorder, onSelect, onToggle }) => {
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = (event) => {
    const { active, over } = event;

    if (active.id !== over.id) {
      const oldIndex = banners.findIndex((b) => b.id === active.id);
      const newIndex = banners.findIndex((b) => b.id === over.id);
      const newOrder = arrayMove(banners, oldIndex, newIndex);
      onReorder(newOrder);
    }
  };

  if (!Array.isArray(banners)) {
    return <div className={styles.container}>No banners data available.</div>;
  }

  return (
    <div className={styles.container}>
      <h2 className={styles.title}>Banners</h2>
      <DndContext 
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext 
          items={banners.map(b => b.id)}
          strategy={verticalListSortingStrategy}
        >
          <div className={styles.list}>
            {banners.map((banner) => (
              <BannerListRow 
                key={banner.id} 
                banner={banner} 
                onClick={() => onSelect(banner)}
                onToggle={(val) => onToggle(banner.id, val)}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>
    </div>
  );
};

export default BannerList;
