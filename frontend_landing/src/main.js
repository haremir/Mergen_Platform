import anime from 'animejs';
import { initMatrixCanvas } from './canvas.js';

document.addEventListener('DOMContentLoaded', () => {
  // 1. Matrix Background
  initMatrixCanvas();

  // 2. Footer Clock
  const clockEl = document.getElementById('clock');
  if (clockEl) {
    setInterval(() => {
      const now = new Date();
      clockEl.textContent = `${now.toTimeString().split(' ')[0]}`;
    }, 1000);
  }

  // 3. Anime.js Entrance Animations
  anime.timeline({ easing: 'easeOutCubic' })
    .add({
      targets: '#hero-logo-stage',
      scale: [0.8, 1],
      opacity: [0, 1],
      duration: 800
    })
    .add({
      targets: '.hero-title',
      opacity: [0, 1],
      translateY: [20, 0],
      duration: 800,
      offset: '-=400'
    })
    .add({
      targets: '.hero-desc',
      opacity: [0, 1],
      translateY: [15, 0],
      duration: 600,
      offset: '-=500'
    })
    .add({
      targets: '.hero-actions .btn-nothing',
      opacity: [0, 1],
      translateY: [10, 0],
      delay: anime.stagger(150),
      duration: 600,
      offset: '-=400'
    });

  // Scroll animations for sections
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        anime({
          targets: entry.target.querySelectorAll('.glass, .product-card'),
          opacity: [0, 1],
          translateY: [25, 0],
          duration: 700,
          easing: 'easeOutCubic'
        });
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.15 });

  document.querySelectorAll('.section').forEach(el => observer.observe(el));

  // 4. Kâtip Studio Interaction
  initKatipStudio();

  // 5. Dental Sim Interaction
  initDentalSim();
});

function initKatipStudio() {
  const generateBtn = document.getElementById('generate-btn');
  const consoleBox = document.getElementById('katip-console');
  const topicChips = document.querySelectorAll('.topic-chip');

  if (!generateBtn || !consoleBox) return;

  let activeTopic = 'Yapay Zeka & İş Dünyası';

  topicChips.forEach(chip => {
    chip.addEventListener('click', () => {
      topicChips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      activeTopic = chip.getAttribute('data-topic');
    });
  });

  const contentMap = {
    'Yapay Zeka & İş Dünyası': `[SEO BLOG] Yapay Zeka Çağında Otonom İşletmeler

Geleceğin başarılı ajansları ve kurumsal şirketleri, içerik süreçlerini otonom yapay zeka ile hızlandırıyor.

📍 SEO Başlık: 2026'da Dijitalleşme
📍 Marka Tonu: Kurumsal & Yenilikçi
✔ Sosyal Medya Taslağı Hazırlandı.`,

    'Diş Hekimliğinde Dijital Dönüşüm': `[SEO BLOG] Diş Kliniklerinde Akıllı Anamnez Dönemi

Hasta randevu sürecini otomatik hale getiren ve doğru uzman doktor eşleşmesi sağlayan yeni diş klinik yaklaşımı.

📍 Kategori: Diş Sağlığı & Teknoloji
✔ DentBot Entegrasyonu Aktif.`,

    'E-Ticarette Dönüşüm Rehberi': `[SEO BLOG] E-Ticarette İkna Edici İçerik Metinleri

Müşteri dönüşüm oranlarını artıran özgün ürün ve blog yazısı kurguları.

📍 Dönüşüm Skoru: %98
✔ Çoklu Platform Taslağı Hazır.`
  };

  generateBtn.addEventListener('click', () => {
    generateBtn.disabled = true;
    consoleBox.innerHTML = '<span style="color: var(--cyan);">// KÂTİP İÇERİK OLUŞTURUYOR...</span>\n\n';

    const targetText = contentMap[activeTopic] || contentMap['Yapay Zeka & İş Dünyası'];
    let idx = 0;

    function typeChar() {
      if (idx < targetText.length) {
        consoleBox.innerHTML += targetText.charAt(idx);
        idx++;
        setTimeout(typeChar, 15);
      } else {
        generateBtn.disabled = false;
      }
    }
    typeChar();
  });
}

function initDentalSim() {
  const msgContainer = document.getElementById('dental-sim-messages');
  const simBtns = document.querySelectorAll('.sim-btn');

  if (!msgContainer) return;

  const scenarios = {
    gece_agrisi: [
      { sender: 'user', text: 'Dişimde 2 gündür gece uykudan uyandıran şiddetli ağrı var.' },
      { sender: 'bot', text: 'Geçmiş olsun! Gece uykudan uyandıran diş ağrıları pulpa iltihaplanmasına işaret edebilir. İlaç veya kronik alerjiniz var mı?' },
      { sender: 'user', text: 'Hayır, kronik hastalığım yok.' },
      { sender: 'bot', text: '✅ **Slot Eşleşti:** Dr. Dt. Selin Yılmaz (Endodonti Uzmanı)\n📅 **Saat:** Bugün 16:30 (Hekim Onayına İletildi) 🔔' }
    ],
    seffaf_plak: [
      { sender: 'user', text: 'Ortodonti şeffaf plak tedavisi için bilgi almak istiyorum.' },
      { sender: 'bot', text: 'Telsiz ortodonti tedavimiz için Dr. Dt. Kaan Öztürk (Ortodonti Uzmanı) muayenesini ayarlamamı ister misiniz?' },
      { sender: 'user', text: 'Evet, uygun zamanı ayarlayabiliriz.' },
      { sender: 'bot', text: '✅ **Slot Eşleşti:** Cuma 14:30 (Hekim Onay Paneline İletildi)' }
    ]
  };

  simBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const type = btn.getAttribute('data-type');
      const flow = scenarios[type];
      if (!flow) return;

      msgContainer.innerHTML = '<div class="msg bot"><span>🦷 Merhaba! Diş şikayetinizi kısaca belirtebilir misiniz?</span></div>';

      let step = 0;
      function addNextMsg() {
        if (step < flow.length) {
          const item = flow[step];
          const div = document.createElement('div');
          div.className = `msg ${item.sender}`;
          div.innerHTML = `<span>${item.text.replace(/\n/g, '<br>')}</span>`;
          msgContainer.appendChild(div);
          msgContainer.scrollTop = msgContainer.scrollHeight;

          step++;
          setTimeout(addNextMsg, 900);
        }
      }
      addNextMsg();
    });
  });
}
