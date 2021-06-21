_ЛК &#xab;ТНС Энерго&#xbb;_ для _Home Assistant_
==================================================

> Предоставление информации о текущем состоянии ваших аккаунтов в ЛК ТНС Энерго.
>
>[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
> [![Лицензия](https://img.shields.io/badge/%D0%9B%D0%B8%D1%86%D0%B5%D0%BD%D0%B7%D0%B8%D1%8F-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
> [![Поддержка](https://img.shields.io/badge/%D0%9F%D0%BE%D0%B4%D0%B4%D0%B5%D1%80%D0%B6%D0%B8%D0%B2%D0%B0%D0%B5%D1%82%D1%81%D1%8F%3F-%D0%B4%D0%B0-green.svg)](https://github.com/alryaz/hass-tns-energo/graphs/commit-activity)
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
3. Найдите `TNS Energo` (`ТНС Энерго`) в поиске по интеграциям <sup>1</sup>
4. Установите последнюю версию компонента, нажав на кнопку `Установить` (`Install`)
5. Перезапустите Home Assistant


### Вручную

> **⚠️ Не рекомендуется**

## Конфигурация компонента:
- Вариант А: Через _Интеграции_ (в поиске - "ТНС Энерго" или "TNS Energo")
- Вариант Б: YAML

### Пример конфигурации YAML
```yaml
tns_energo:
  username: 1234567890
  password: super_password
```
