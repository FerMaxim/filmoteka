const $ = s => document.querySelector(s);
const works = [
 {title:'Тихая орбита',kind:'Фильм, 2025',color:'#748baf',text:'Для вечера, когда хочется немного тишины. История о расстоянии между людьми, даже если они рядом.'},
 {title:'Город после дождя',kind:'Анимация, 2024',color:'#5d8d8b',text:'Здесь хочется задержаться ради света в окнах и маленьких, очень человеческих историй.'},
 {title:'Последний поезд к морю',kind:'Сериал, 2023',color:'#ab8c77',text:'Медленное путешествие, которое неожиданно становится разговором с собой.'},
 {title:'Сад далёких голосов',kind:'Аниме, 2025',color:'#8b789c',text:'О памяти и том, как научиться отпускать. Советую смотреть без спешки.'}
];
const saved = new Map(); let tab = 'Рекомендации';
function cards(target, list, recommendations=false){
 target.replaceChildren();
 if(!list.length){const p=document.createElement('p');p.textContent='Здесь пока пусто. Выберите произведение в каталоге.';const a=document.createElement('a');a.href='#catalog';a.textContent='Открыть каталог';target.append(p,a);return;}
 for(const w of list){const article=document.createElement('article');article.className='card';const poster=document.createElement('div');poster.className='poster';poster.style.setProperty('--art',w.color);poster.dataset.title=w.title;poster.setAttribute('aria-hidden','true');const h=document.createElement('h3');h.textContent=w.title;const meta=document.createElement('p');meta.textContent=w.kind;article.append(poster,h,meta);if(recommendations){const p=document.createElement('p');p.textContent=w.text;article.append(p);}if(saved.has(w.title)){const p=document.createElement('p');p.textContent=`Моя оценка: ${saved.get(w.title)}`;article.append(p);}const b=document.createElement('button');b.textContent='Оценить';b.onclick=()=>{$('#work-title').textContent=w.title;location.hash='rating';};article.append(b);target.append(article);}
}
function library(){cards($('#library'),tab==='Рекомендации'?works:tab==='Оценённое'?works.filter(w=>saved.has(w.title)):[],tab==='Рекомендации');}
function route(){const id=['profile','catalog','rating'].includes(location.hash.slice(1))?location.hash.slice(1):'profile';for(const s of document.querySelectorAll('main>section'))s.hidden=s.id!==id;for(const a of document.querySelectorAll('header nav a')){if(a.hash==='#'+id)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');}window.scrollTo(0,0);}
window.addEventListener('hashchange',route);route();library();cards($('#catalog-grid'),works);
for(const b of document.querySelectorAll('.tabs button'))b.onclick=()=>{tab=b.textContent;for(const other of document.querySelectorAll('.tabs button'))other.setAttribute('aria-pressed',String(other===b));library();};
$('#scene').onclick=()=>{const scene=$('.scene');scene.hidden=!scene.hidden;$('#scene').textContent=scene.hidden?'Показать сцену':'Скрыть сцену';};
$('#search').oninput=e=>{const list=works.filter(w=>w.title.toLocaleLowerCase('ru').includes(e.target.value.toLocaleLowerCase('ru').trim()));cards($('#catalog-grid'),list);$('#search-status').textContent=list.length?'':'Ничего не найдено. Измените название или очистите поиск.';};
for(const name of ['Сюжет','Персонажи','Визуальная составляющая','Звуковое сопровождение','Атмосфера','Вовлечённость','Послевкусие']){const label=document.createElement('label');label.textContent=name;const input=document.createElement('input');input.type='number';input.min=0;input.max=10;input.step=1;input.placeholder='Не указано';label.append(input);$('#criteria').append(label);}
for(const emotion of ['Радость','Грусть','Удивление','Тревога','Нежность']){const label=document.createElement('label');const input=document.createElement('input');input.type='checkbox';label.append(input,emotion);$('.emotions').append(label);}
function calculate(){const inputs=[...document.querySelectorAll('input[type=number]')];if(inputs.some(i=>!i.validity.valid)||!inputs[0].value)return null;const extra=inputs.slice(1).filter(i=>i.value!=='').map(i=>Number(i.value));const i=Number(inputs[0].value);return (extra.length?(i+extra.reduce((a,b)=>a+b,0)/extra.length)/2:i).toFixed(1);}
$('form').oninput=()=>{$('#total').textContent=calculate()??'—';$('#form-status').textContent='';};
$('form').onsubmit=e=>{e.preventDefault();const total=calculate();if(total===null){$('#form-status').textContent='Укажите общее впечатление и числа от 0 до 10 с шагом 1.';[...document.querySelectorAll('input[type=number]')].find(i=>!i.validity.valid)?.focus();return;}saved.set($('#work-title').textContent,total);library();$('#form-status').textContent='Оценка сохранена до перезагрузки. Она появилась в «Оценённом».';};
