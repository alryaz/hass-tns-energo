_ЛК &#xab;ТНС Энерго&#xbb;_ для _Home Assistant_
==================================================
<img src="https://raw.githubusercontent.com/alryaz/hass-lkcomu-interrao/master/images/header.png" alt="Логотип интеграции">

> Предоставление информации о текущем состоянии ваших аккаунтов в ЕЛК ЖКХ.
>
>[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
> [![Лицензия](https://img.shields.io/badge/%D0%9B%D0%B8%D1%86%D0%B5%D0%BD%D0%B7%D0%B8%D1%8F-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
> [![Поддержка](https://img.shields.io/badge/%D0%9F%D0%BE%D0%B4%D0%B4%D0%B5%D1%80%D0%B6%D0%B8%D0%B2%D0%B0%D0%B5%D1%82%D1%81%D1%8F%3F-%D0%B4%D0%B0-green.svg)](https://github.com/alryaz/hass-lkcomu-interrao/graphs/commit-activity)
>
>[![Пожертвование Yandex](https://img.shields.io/badge/%D0%9F%D0%BE%D0%B6%D0%B5%D1%80%D1%82%D0%B2%D0%BE%D0%B2%D0%B0%D0%BD%D0%B8%D0%B5-Yandex-red.svg)](https://money.yandex.ru/to/410012369233217)
> [![Пожертвование PayPal](https://img.shields.io/badge/%D0%9F%D0%BE%D0%B6%D0%B5%D1%80%D1%82%D0%B2%D0%BE%D0%B2%D0%B0%D0%BD%D0%B8%D0%B5-Paypal-blueviolet.svg)](https://www.paypal.me/alryaz)

## Введение

> @ TODO @

## Установка

### Посредством HACS

> **✔️️ Рекомендуемый метод**

1. Установите
   HACS ([инструкция по установке на оф. сайте](https://hacs.xyz/docs/installation/installation/))
2. Добавьте репозиторий в список дополнительных
3. Найдите `energosbyt` в поиске по интеграциям <sup>1</sup>
4. Установите последнюю версию компонента, нажав на кнопку `Установить` (`Install`)
5. Перезапустите Home Assistant

_<sup>1</sup> При поиске может появиться компонент `Мосэнергосбыт`. Это предшествующая данному
проекту интеграция, и будет в скором времени упразднена._

### Вручную

> **⚠️ Не рекомендуется**

1. Скачайте архив с исходным кодом дополнения
2. Извлеките папку `lkcomu_interrao` из архива в папку `custom_components` внутри папки с
   конфигурацией Home Assistant (создайте её, если она отсутствует)
3. Перезапустите Home Assistant

## Настройка

### Через раздел интеграции
1. Перейдите в подраздел _"[Интеграции](https://my.home-assistant.io/redirect/integrations)"_ в разделе _"Настройки"_
2. Нажмите кнопку _"Добавить интеграцию"_
3. Введите в поисковую строку: **_Личный кабинет Интер РАО (Энергосбыт)_** (англ. **_Inter RAO Personal Cabinet (Energosbyt)_**)
4. Выберите найденную интеграцию
5. Следуйте инструкциям мастера по добавлению