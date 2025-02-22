// include the FspTimer library
#include "FspTimer.h"
// define the timer objects
FspTimer slow_7_timer;
FspTimer slow_8_timer;
// pin states variables
bool slowPin7State = false; 
bool slowPin8State = true; 
// callback method used by timer
void slow_7_callback(timer_callback_args_t __attribute((unused)) *p_args) {
  digitalWrite(7, slowPin7State);
  slowPin7State = !slowPin7State;
}
void slow_8_callback(timer_callback_args_t __attribute((unused)) *p_args) {
  digitalWrite(8, slowPin8State);
  slowPin8State = !slowPin8State;
}
// timer initialization functions
bool beginSlow7Timer(float rate) {
  uint8_t timer_type = GPT_TIMER;
  int8_t tindex = FspTimer::get_available_timer(timer_type);
  if (tindex < 0){
    tindex = FspTimer::get_available_timer(timer_type, true);
  }
  if (tindex < 0){
    return false;
  }
  FspTimer::force_use_of_pwm_reserved_timer();
  if(!slow_7_timer.begin(TIMER_MODE_PERIODIC, timer_type, tindex, rate, 0.0f, slow_7_callback)){
    return false;
  }
  if (!slow_7_timer.setup_overflow_irq()){
    return false;
  }
  if (!slow_7_timer.open()){
    return false;
  }
  if (!slow_7_timer.start()){
    return false;
  }
  return true;
}
bool beginSlow8Timer(float rate) {
  uint8_t timer_type = GPT_TIMER;
  int8_t tindex = FspTimer::get_available_timer(timer_type);
  if (tindex < 0){
    tindex = FspTimer::get_available_timer(timer_type, true);
  }
  if (tindex < 0){
    return false;
  }
  FspTimer::force_use_of_pwm_reserved_timer();
  if(!slow_8_timer.begin(TIMER_MODE_PERIODIC, timer_type, tindex, rate, 0.0f, slow_8_callback)){
    return false;
  }
  if (!slow_8_timer.setup_overflow_irq()){
    return false;
  }
  if (!slow_8_timer.open()){
    return false;
  }
  if (!slow_8_timer.start()){
    return false;
  }
  return true;
}
// setup function
void setup() {
  pinMode(7, OUTPUT);
  pinMode(8, OUTPUT);

  beginSlow7Timer(100); // 50 Hz at 50% duty cycle
  beginSlow8Timer(100);
}
// intterupt handled by callback, so loop is empty
void loop() {}