# Előfeltételek
 1. Fejlsztői kofiguráció:AMD Ryzen 5 4600h, Nvidia GeForce GTX 1650 Ti Mobile, 16Gb Memória, 60 Gb szabad tárhely(az operációs rendszerrel egyyüttes tárhely)
 2. Ubuntu 22.04.5 rendszeren indítható el kizárólag a szimuláció

# Telepítés
A repository letöltése előtt szükséges készíteni 2 mappát ahhoz, hogy megfelelően működjön a projekt:
  + Tetszőleges nevű főmappa
  + src mappa-> a főmappába
    
Ezek létrehozását követően git clone segítségével vagy .zip fájl letöltése és kicsomagolásával a projektet elhelyezzük az src mappába.
Következő lépésben belelépünk a two_wheeled_robot mappába majd a következő parancsot futtatjuk
  ```
./install_dependencies.sh
```
Ezzel a futtatáshoz szükséges csomagok települnek fel.Ez követően lefordítjuk a programot a 
```
colcon build
```
parancsal.
# Futtatás
Buildelés után az
```
./auto_traiin_watchdog.sh
```
parancs lefuttatását követően ki kell választanunk a tanulási módot. A kamera kép alapú (1) képfeldolgozással határozza meg a jutalmakat, míga a koordináta alapú (2) a CatMull-Rom Spline pontjai és a robot koordinátája alapján jutalmaz.
A következő választás a futtatás módja. Az első opció választása esetén látszódni fog a szimuláció viszont jobban megterheli a hardvert, főként debug-ra használatos, amásodig opiónál nem fog elindulni vizuálisan a szimuláció ezzel a tanulás is gyorsabban halad.
Főként a második opciónál ajánlott használni az `rqt` programot amivel a kamera képét lehet figyelni. Ehhez nyissunk egy új terminált és futtassuk le a következő paracsokat:
```
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_LOCALHOST_ONLY=1
export ROS_DOMAIN_ID=42
```

Ezek azért szükségesek mivel leválasztottam a gazebo szerveréről a projektet, így egyszere egy hálózaton több szmuláció is futtatható. Ezt követően az `rqt` paranccsal tudjuk nézzzni a kameraképet a `Plugins--> Visualization--> Image View` pont alatt.

# Paraméterek állítása és monitorozás
## Paraméterek
A tanítás sikerességéhez szükség lesz időnként változtatni a PPO algoritmus hiperparaméterein, amikre főként ügyelni kell a következők:

+ learning_rate:Ez adaja meg mennyire gyorsan tanul a rendszer
+ n_steps:Azt mutatja mennyi lépést tesz meg mielőtt mentene a rendszer, növelni érdemes amikor egy epizód kb a felét éri el az n_steps-nek
+ ent_coef: Az explorációért felelős, 0 és 0.05 közötti értékekkel teszteletem a a projektet és stabil fejlődést mutatott 

Minden változtatás után szükséges újra lefordítani a projjektet a fentebb leírt módon.

## Monitorozás

A robot fejlődésének monitorozására TensorBoardot hasznátam amivel lehet visszamenőleg is ellenőrizni a robot fejlődését. Az első mentés lefutása után egy új terminálban a következő paracsot kell lefuttani, valamint a localhost linkre kattintani az értékek vizsgálatához:

```
tensorboard --logrdir ppo_line_follower_vision
```
a képfeldolgozó módhoz, vagy

```
tensorboard --logrdir ppo_line_follower_vision
```
a koordináta módhoz. Itt a `SCALARS` fülre kattintava és a bal oltalon az `Ignore outliers in chart scaling` pipát kivéve látszódni fognak a gráfok amiből a legfntosabbak:
+ `ep_rew_mean`, ami az epizódonkénti átlag jutamat mutatja
+ `ep_len_mean`, epizódok átlag lépéshosszát mutatja
+ `entropy_loss`, az algoritmus bizonytalanságát mutatja minél alacsonyabb annál jobb

# Tesztelés

A tesztelére 2 script szolgál amelyből az egyik a `start_evaluationn.sh`, ami azokon a pályákon teszteli a modellt amin betanult.
```
./start_evaluation.sh
```
A másik a `start_testing.sh`, ami a modell számára teljesen ismeretlen pályákon tesztel.
```
./start_testing.sh
```
Jelenlegi tapasztalataim alapján 1.5-2 milló lépés és hiperparaméter módosítások után fel lehet tanítani a robotot vonal követésre.
