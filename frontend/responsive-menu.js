/* =========   RESPONSIVE MOBILE MENU HANDLER   ========= */
function initializeResponsiveMenu() {
  const sidebarToggle = document.getElementById('sidebar-toggle');
  const sidebar = document.getElementById('sidebar');
  const sidebarOverlay = document.getElementById('sidebar-overlay');
  const sidebarClose = document.getElementById('sidebar-close');

  // Toggle sidebar on mobile
  if (sidebarToggle) {
    sidebarToggle.addEventListener('click', () => {
      sidebar?.classList.add('mobile-open');
      sidebarOverlay?.classList.add('active');
      document.body.style.overflow = 'hidden';
    });
  }

  // Close sidebar
  function closeSidebar() {
    sidebar?.classList.remove('mobile-open');
    sidebarOverlay?.classList.remove('active');
    document.body.style.overflow = '';
  }

  if (sidebarClose) {
    sidebarClose.addEventListener('click', closeSidebar);
  }

  if (sidebarOverlay) {
    sidebarOverlay.addEventListener('click', closeSidebar);
  }

  // Close sidebar on escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && sidebar?.classList.contains('mobile-open')) {
      closeSidebar();
    }
  });

  // Handle window resize - close sidebar if switching to desktop
  window.addEventListener('resize', () => {
    if (window.innerWidth >= 768) {
      closeSidebar();
    }
  });
}

// Initialize responsive menu when DOM is loaded
document.addEventListener('DOMContentLoaded', initializeResponsiveMenu);